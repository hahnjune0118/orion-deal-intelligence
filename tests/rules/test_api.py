import hashlib
import io
import json
import pytest

from orion.web.rules_app import create_rules_app


@pytest.fixture
def app(tmp_path):
    app=create_rules_app(tmp_path);app.testing=True
    return app


def post(client,url,data):
    return client.post(url,json=data,headers={'Origin':'http://localhost'})


def test_origin_boundary_and_no_ai(app):
    c=app.test_client()
    assert c.post('/api/example',json={}).status_code==403
    assert c.get('/healthz').get_json()['live_provider'] is False
    assert c.get('/',headers={'Host':'attacker.example'}).status_code==403
    assert c.post('/api/example',json={},headers={'Origin':'https://other.example'}).status_code==403


def test_project_survives_app_restart_and_files_are_project_bound(app,tmp_path):
    c=app.test_client();d=post(c,'/api/example',{}).get_json()
    p=d['id'];doc=d['state']['documents'][0]
    r=c.get(f'/api/projects/{p}/files/{doc["id"]}')
    assert hashlib.sha256(r.data).hexdigest()==doc['sha256']
    other=post(c,'/api/projects',dict(company='다른 기업',period='2025',industry='general')).get_json()
    assert c.get(f'/api/projects/{other["id"]}/files/{doc["id"]}').status_code==400
    restarted=create_rules_app(tmp_path);restarted.testing=True
    assert restarted.test_client().get('/api/projects/'+p).get_json()['version']==d['version']


def test_preview_is_pure_and_stale_or_invalid_apply_is_atomic(app):
    c=app.test_client();d=post(c,'/api/example',{}).get_json();p=d['id'];version=d['version']
    body=dict(version=version,question='recurring.definition',outcome='support',note='근거를 검토했습니다.',response='계약 정의를 확인했습니다.',group='contract',reviewed=True)
    r=post(c,f'/api/projects/{p}/preview',body)
    assert r.status_code==200
    assert r.get_json()['after']['probabilities']['recurring']==pytest.approx(24/38)
    assert c.get('/api/projects/'+p).get_json()['version']==version
    body['reviewed']=False
    assert post(c,f'/api/projects/{p}/actions/evidence',body).status_code==400
    body['reviewed']=True
    applied=post(c,f'/api/projects/{p}/actions/evidence',body).get_json()
    assert applied['version']==version+1
    assert post(c,f'/api/projects/{p}/actions/evidence',body).status_code==409
    body['version']=applied['version'];body['span']='not-in-this-project'
    assert post(c,f'/api/projects/{p}/actions/evidence',body).status_code==400
    assert c.get('/api/projects/'+p).get_json()['version']==applied['version']


def test_upload_search_original_and_deduplication(app):
    c=app.test_client();p=post(c,'/api/projects',dict(company='분석 기업',period='2025',industry='general')).get_json()
    raw='매출 100억원은 원문 기재값입니다.\n고객 계약과 수금 자료를 확인해야 합니다.'.encode()
    def upload():
        return c.post(f'/api/projects/{p["id"]}/documents',data={'version':str(p['version']),'file':(io.BytesIO(raw),'자료.txt')},headers={'Origin':'http://localhost'})
    r=upload();assert r.status_code==200
    p=r.get_json();doc=p['state']['documents'][0]
    assert doc['sha256']==hashlib.sha256(raw).hexdigest()
    again=upload();assert len(again.get_json()['state']['documents'])==1
    search=c.get(f'/api/projects/{p["id"]}/search?q=매출').get_json()
    assert search[0]['text']=='매출 100억원은 원문 기재값입니다.'
    assert c.get(f'/api/projects/{p["id"]}/files/{doc["id"]}').data==raw
    analyzed=post(c,f'/api/projects/{p["id"]}/actions/analyze',{'version':p['version']}).get_json()
    assert any('100억원' in f['numbers'] for f in analyzed['state']['findings'])


def test_failed_upload_does_not_create_file_or_change_project(app):
    c=app.test_client();p=post(c,'/api/projects',dict(company='기업',period='2025',industry='general')).get_json()
    r=c.post(f'/api/projects/{p["id"]}/documents',data={'version':str(p['version']),'file':(io.BytesIO(b'not a PDF'),'bad.pdf')},headers={'Origin':'http://localhost'})
    assert r.status_code==400
    assert c.get('/api/projects/'+p['id']).get_json()['version']==p['version']


def test_snapshot_history_csv_and_json_export(app):
    c=app.test_client();p=post(c,'/api/example',{}).get_json();pid=p['id']
    assert len(c.get(f'/api/projects/{pid}/history').get_json())==2
    exported=c.get(f'/api/projects/{pid}/export/json').get_json()
    assert exported['state']['policy']=='adaptive-rules-1.0.0'
    csv=c.get(f'/api/projects/{pid}/export/csv').data.decode('utf-8-sig')
    assert 'EIG(bits)' in csv and 'recurring.definition' in csv
