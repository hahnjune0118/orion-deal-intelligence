"""Single-user local SQLite projects, immutable files and atomic version snapshots."""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import engine


class Conflict(ValueError):
    pass


class Store:
    def __init__(self,path):
        self.path=str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, version INTEGER, state TEXT);
                CREATE TABLE IF NOT EXISTS files(project TEXT, id TEXT, filename TEXT, sha TEXT, data BLOB,
                    PRIMARY KEY(project,id), FOREIGN KEY(project) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS snapshots(project TEXT, version INTEGER, body TEXT,
                    PRIMARY KEY(project,version), FOREIGN KEY(project) REFERENCES projects(id));
            ''')

    @contextmanager
    def connection(self):
        c=sqlite3.connect(self.path,timeout=10)
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:
                yield c
        finally:
            c.close()

    def list(self):
        with self.connection() as c:
            return [dict(id=p,version=v,company=json.loads(s)['company'],period=json.loads(s)['period'])
                    for p,v,s in c.execute('SELECT id,version,state FROM projects ORDER BY rowid DESC')]

    def create(self,company,period,industry):
        state=engine.initial(company,period,industry)
        identifier=uuid4().hex
        with self.connection() as c:
            c.execute('INSERT INTO projects VALUES(?,?,?)',(identifier,1,json.dumps(state,ensure_ascii=False)))
            c.execute('INSERT INTO snapshots VALUES(?,?,?)',(identifier,1,json.dumps(engine.snapshot(state),ensure_ascii=False)))
        return self.get(identifier)

    def import_case(self,state,files):
        """Commit a prepared anonymized case and its text derivatives together."""
        identifier=uuid4().hex
        body=json.dumps(state,ensure_ascii=False)
        snapshot=json.dumps(engine.snapshot(state),ensure_ascii=False)
        if len(body)>20_000_000:
            raise ValueError('사례 데이터 한도를 초과했습니다.')
        with self.connection() as c:
            c.execute('INSERT INTO projects VALUES(?,?,?)',(identifier,1,body))
            for file in files:
                c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(identifier,*file))
            c.execute('INSERT INTO snapshots VALUES(?,?,?)',(identifier,1,snapshot))
        return self.get(identifier)

    def get(self,identifier):
        with self.connection() as c:
            row=c.execute('SELECT version,state FROM projects WHERE id=?',(identifier,)).fetchone()
            if not row:
                raise ValueError('프로젝트를 찾지 못했습니다.')
            previous=c.execute('SELECT version,body FROM snapshots WHERE project=? ORDER BY version DESC LIMIT 2',(identifier,)).fetchall()
        state=json.loads(row[1])
        return dict(id=identifier,version=row[0],state=state,
                    snapshots=[dict(version=v,**json.loads(body)) for v,body in previous])

    def update(self,identifier,version,operation,*,file=None):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT version,state FROM projects WHERE id=?',(identifier,)).fetchone()
            if not row:
                raise ValueError('프로젝트를 찾지 못했습니다.')
            if type(version) is not int or row[0] != version:
                raise Conflict('다른 화면에서 자료가 변경됐습니다. 최신 상태를 불러온 뒤 다시 검토하세요.')
            state=json.loads(row[1])
            operation(state)
            if len(json.dumps(state))>20_000_000:
                raise ValueError('프로젝트 데이터 한도입니다. 자료를 나누어 검토하세요.')
            c.execute('UPDATE projects SET version=?,state=? WHERE id=?',
                      (version+1,json.dumps(state,ensure_ascii=False),identifier))
            if file:
                c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(identifier,*file))
            c.execute('INSERT INTO snapshots VALUES(?,?,?)',
                      (identifier,version+1,json.dumps(engine.snapshot(state),ensure_ascii=False)))
        return self.get(identifier)

    def file(self,project,identifier):
        with self.connection() as c:
            row=c.execute('SELECT filename,data,sha FROM files WHERE project=? AND id=?',(project,identifier)).fetchone()
        if not row:
            raise ValueError('현재 프로젝트의 원문 파일이 아닙니다.')
        import hashlib
        if hashlib.sha256(row[1]).hexdigest()!=row[2]:
            raise ValueError('원본 파일 해시가 일치하지 않습니다.')
        return row[0],row[1]

    def history(self,project):
        self.get(project)
        with self.connection() as c:
            return [dict(version=v,**json.loads(s)) for v,s in c.execute(
                'SELECT version,body FROM snapshots WHERE project=? ORDER BY version',(project,))]
