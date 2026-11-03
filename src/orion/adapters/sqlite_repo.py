"""SQLite persistence boundary for trusted application services.

This adapter does not rank, approve, or infer domain transitions. Review services
authorize their actor and calculate a complete change *inside* ``transact``.
Public Demo must never instantiate this repository. The database owner's access
is not a tamper-proof ledger or security boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterator, Mapping

from pydantic import BaseModel

from orion.domain.models import DealState, ENTITY_MODELS, StagedEvidenceUpdate
from orion.domain.grounding import validate_grounding

COLLECTIONS = {
    "Document": "documents", "SourceSpan": "source_spans", "Thesis": "theses",
    "Claim": "claims", "Evidence": "evidence", "EvidenceRelation": "evidence_relations",
    "DDQuestion": "dd_questions", "RankingSnapshot": "ranking_snapshots",
    "AnalystDecision": "analyst_decisions", "AuditEvent": "audit_events",
    "AnalysisRun": "analysis_runs",
}
IMMUTABLE_TYPES = frozenset({"RankingSnapshot", "AnalystDecision", "AuditEvent"})


def canonical_json(value: Any) -> str:
    """Contract JSON: UTF-8, stable keys, no whitespace and no NaN/Infinity."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def payload_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class RepositoryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class RepositoryCommitResult:
    state_revision: int
    snapshot_id: str
    replayed: bool = False


DDL = """
CREATE TABLE IF NOT EXISTS deals (
    deal_id TEXT PRIMARY KEY,
    contract_version TEXT NOT NULL CHECK(contract_version='1.0.0'),
    mode TEXT NOT NULL CHECK(mode IN ('demo','local_live')),
    state_revision INTEGER NOT NULL CHECK(state_revision>=0),
    head_snapshot_id TEXT,
    FOREIGN KEY(deal_id,head_snapshot_id) REFERENCES snapshots(deal_id,snapshot_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS source_blobs (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    sha256 TEXT NOT NULL CHECK(length(sha256)=64),
    byte_size INTEGER NOT NULL CHECK(byte_size>=0),
    content BLOB NOT NULL CHECK(length(content)=byte_size),
    PRIMARY KEY(deal_id,sha256)
);
CREATE TABLE IF NOT EXISTS entity_versions (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_version INTEGER NOT NULL CHECK(entity_version>=1),
    source_sha256 TEXT,
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,entity_type,entity_id,entity_version),
    FOREIGN KEY(deal_id,source_sha256) REFERENCES source_blobs(deal_id,sha256),
    CHECK(json_extract(payload,'$.id')=entity_id),
    CHECK(json_extract(payload,'$.entity_version')=entity_version),
    CHECK((entity_type='Deal' AND entity_id=deal_id) OR
          (entity_type!='Deal' AND json_extract(payload,'$.deal_id')=deal_id))
);
CREATE TABLE IF NOT EXISTS snapshots (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    snapshot_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'RankingSnapshot' CHECK(entity_type='RankingSnapshot'),
    entity_version INTEGER NOT NULL CHECK(entity_version=1),
    state_revision INTEGER NOT NULL CHECK(state_revision>=1),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,snapshot_id),
    UNIQUE(deal_id,state_revision),
    FOREIGN KEY(deal_id,entity_type,snapshot_id,entity_version)
      REFERENCES entity_versions(deal_id,entity_type,entity_id,entity_version)
);
CREATE TABLE IF NOT EXISTS decisions (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    decision_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'AnalystDecision' CHECK(entity_type='AnalystDecision'),
    entity_version INTEGER NOT NULL CHECK(entity_version=1),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,decision_id),
    FOREIGN KEY(deal_id,entity_type,decision_id,entity_version)
      REFERENCES entity_versions(deal_id,entity_type,entity_id,entity_version)
);
CREATE TABLE IF NOT EXISTS audit_events (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    audit_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'AuditEvent' CHECK(entity_type='AuditEvent'),
    entity_version INTEGER NOT NULL CHECK(entity_version=1),
    sequence INTEGER NOT NULL CHECK(sequence>=1),
    decision_id TEXT,
    before_snapshot_id TEXT,
    after_snapshot_id TEXT,
    event_hash TEXT NOT NULL,
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,audit_id),
    UNIQUE(deal_id,sequence),
    FOREIGN KEY(deal_id,entity_type,audit_id,entity_version)
      REFERENCES entity_versions(deal_id,entity_type,entity_id,entity_version),
    FOREIGN KEY(deal_id,decision_id) REFERENCES decisions(deal_id,decision_id),
    FOREIGN KEY(deal_id,before_snapshot_id) REFERENCES snapshots(deal_id,snapshot_id),
    FOREIGN KEY(deal_id,after_snapshot_id) REFERENCES snapshots(deal_id,snapshot_id)
);
CREATE TABLE IF NOT EXISTS processed_commands (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    idempotency_key TEXT NOT NULL CHECK(length(idempotency_key)>0),
    request_digest TEXT NOT NULL CHECK(length(request_digest)=64),
    result_revision INTEGER NOT NULL CHECK(result_revision>=1),
    snapshot_id TEXT NOT NULL,
    PRIMARY KEY(deal_id,idempotency_key),
    FOREIGN KEY(deal_id,snapshot_id) REFERENCES snapshots(deal_id,snapshot_id),
    FOREIGN KEY(deal_id,result_revision) REFERENCES snapshots(deal_id,state_revision)
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    run_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'AnalysisRun' CHECK(entity_type='AnalysisRun'),
    entity_version INTEGER NOT NULL CHECK(entity_version>=1),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,run_id,entity_version),
    FOREIGN KEY(deal_id,entity_type,run_id,entity_version)
      REFERENCES entity_versions(deal_id,entity_type,entity_id,entity_version)
);
-- Foundation schema only. Reservation/settlement policy is a later service.
CREATE TABLE IF NOT EXISTS budget_ledger (
    ledger_id INTEGER PRIMARY KEY,
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    run_id TEXT NOT NULL,
    run_version INTEGER NOT NULL,
    entry_kind TEXT NOT NULL CHECK(entry_kind IN ('reserve','settle','release','uncertain')),
    amount_usd TEXT NOT NULL CHECK(CAST(amount_usd AS REAL)>=0),
    created_at TEXT NOT NULL,
    FOREIGN KEY(deal_id,run_id,run_version) REFERENCES analysis_runs(deal_id,run_id,entity_version)
);
-- Additive Chunk 2 archives: v1 entity/serialization contracts are unchanged.
CREATE TABLE IF NOT EXISTS staged_updates (
    deal_id TEXT NOT NULL REFERENCES deals(deal_id),
    event_id TEXT NOT NULL,
    payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(deal_id,event_id)
);
CREATE TABLE IF NOT EXISTS staged_resolutions (
    deal_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('approve','reject')),
    decision_id TEXT NOT NULL,
    PRIMARY KEY(deal_id,event_id),
    FOREIGN KEY(deal_id,event_id) REFERENCES staged_updates(deal_id,event_id),
    FOREIGN KEY(deal_id,decision_id) REFERENCES decisions(deal_id,decision_id)
);
CREATE TRIGGER IF NOT EXISTS entity_version_sequence BEFORE INSERT ON entity_versions
BEGIN
 SELECT CASE WHEN NEW.entity_version != COALESCE((SELECT MAX(entity_version)+1
  FROM entity_versions WHERE deal_id=NEW.deal_id AND entity_id=NEW.entity_id),1)
 THEN RAISE(ABORT,'ENTITY_VERSION_CONFLICT') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM entity_versions WHERE deal_id=NEW.deal_id
  AND entity_id=NEW.entity_id AND entity_type!=NEW.entity_type)
 THEN RAISE(ABORT,'ENTITY_ID_CONFLICT') END;
 SELECT CASE WHEN NEW.entity_type IN ('RankingSnapshot','AnalystDecision','AuditEvent')
  AND NEW.entity_version!=1 THEN RAISE(ABORT,'IMMUTABLE_ENTITY') END;
END;
CREATE TRIGGER IF NOT EXISTS deal_revision_sequence BEFORE UPDATE ON deals
BEGIN
 SELECT CASE WHEN NEW.deal_id!=OLD.deal_id OR NEW.mode!=OLD.mode
  OR NEW.contract_version!=OLD.contract_version
 THEN RAISE(ABORT,'DEAL_IDENTITY_IMMUTABLE') END;
 SELECT CASE WHEN NEW.state_revision!=OLD.state_revision+1
 THEN RAISE(ABORT,'REVISION_CONFLICT') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM snapshots WHERE deal_id=NEW.deal_id
  AND snapshot_id=NEW.head_snapshot_id AND state_revision=NEW.state_revision)
 THEN RAISE(ABORT,'HEAD_SNAPSHOT_MISMATCH') END;
END;
"""


def _as_payload(type_name: str, value: Any) -> dict[str, Any]:
    model = ENTITY_MODELS.get(type_name)
    if model is None or type_name not in {"Deal", *COLLECTIONS}:
        raise RepositoryError("UNKNOWN_ENTITY_TYPE", "Unknown persisted entity type")
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    # Revalidate even a caller-created/model_construct or mutated model instance.
    return model.model_validate(value).model_dump(mode="json")


class SQLiteRepository:
    """Per-operation connections, no shared mutable connection or process state.

    ``validation_mode='contract'`` is an explicit test-fixture exception.
    Normal local use defaults to ``local_live`` and rejects fixture approval.
    All callbacks and filesystem paths are server-owned, never browser input.
    """

    def __init__(self, path: str | Path, *, validation_mode: str = "local_live", source_resolver: Any = None):
        if str(path) == ":memory:":
            raise ValueError("Use a file database; independent connections must share durable state")
        if validation_mode not in {"contract", "local_live"}:
            raise ValueError("Repository is local persistence; public Demo has no database")
        self.path = Path(path)
        self.validation_mode = validation_mode
        self.source_resolver = source_resolver

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A fresh configured connection; exposed for diagnostics, not browser use."""
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
            if schema_version not in {0, 1}:
                raise RepositoryError("SCHEMA_VERSION_UNSUPPORTED", "Database needs an explicit schema migration")
            connection.executescript(DDL)
            for table in ("source_blobs", "entity_versions", "snapshots", "decisions", "audit_events",
                          "processed_commands", "analysis_runs", "budget_ledger",
                          "staged_updates", "staged_resolutions"):
                for action in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} "
                                       f"BEFORE {action} ON {table} BEGIN "
                                       "SELECT RAISE(ABORT,'APPEND_ONLY'); END")
            connection.execute("PRAGMA user_version=1")

    def _validate(self, state: Any) -> DealState:
        if isinstance(state, BaseModel):
            state = state.model_dump(mode="json")
        validated = DealState.model_validate(state)
        validate_grounding(validated, mode=self.validation_mode,
                           source_resolver=self.source_resolver).raise_for_errors()
        return validated

    def install_seed(self, state: Any, *, source_blobs: Mapping[str, bytes] | None = None) -> None:
        """Install an authorized initial seed, atomically and only once per deal."""
        validated = self._validate(state)
        payload = validated.model_dump(mode="json")
        deal_id = payload["deal"]["id"]
        if payload["state_revision"] != 1:
            raise RepositoryError("INVALID_SEED", "Seed installation requires revision 1")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if connection.execute("SELECT 1 FROM deals WHERE deal_id=?", (deal_id,)).fetchone():
                    raise RepositoryError("DEAL_EXISTS", "Seed already installed")
                connection.execute("INSERT INTO deals VALUES (?,?,?,0,NULL)",
                                   (deal_id, payload["contract_version"], payload["mode"]))
                writer = RevisionWriter(self, connection, deal_id, 0, None, None)
                for digest, content in (source_blobs or {}).items():
                    writer.put_source_blob(content, expected_sha256=digest)
                writer.put_entity("Deal", payload["deal"])
                for type_name, collection in COLLECTIONS.items():
                    for entity in payload[collection]:
                        writer.put_entity(type_name, entity)
                writer.set_head(payload["head_snapshot_id"])
                connection.execute("UPDATE deals SET state_revision=1,head_snapshot_id=? WHERE deal_id=?",
                                   (writer.head_snapshot_id, deal_id))
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                writer_value = locals().get("writer")
                if writer_value is not None:
                    writer_value._active = False

    def read_state(self, deal_id: str) -> DealState:
        with self.connect() as connection:
            # One read transaction pins all collections and head to one revision.
            connection.execute("BEGIN")
            try:
                state = _read_state(connection, deal_id)
                connection.commit()
                return state
            except BaseException:
                connection.rollback()
                raise

    def transact(self, deal_id: str, *, idempotency_key: str, request_payload: Any,
                 expected_revision: int, mutate: Callable[[RevisionWriter], None]) -> RepositoryCommitResult:
        """Execute an authorized service mutation with revision and replay guards.

        This is only the revision-changing commit primitive. Staging/rejection
        use ``transact_audit``; they never manufacture a ranking revision.

        The service owns ``request_payload`` and must bind all command semantics
        (actor, target/version, action and scope) into it. No command SQL or actor
        supplied by the browser is executed or trusted here.
        """
        return self._transact(deal_id, idempotency_key=idempotency_key, request_payload=request_payload,
                              expected_revision=expected_revision, mutate=mutate, audit_only=False)

    def transact_audit(self, deal_id: str, *, idempotency_key: str, request_payload: Any,
                       expected_revision: int, mutate: Callable[[AuditWriter], None]) -> RepositoryCommitResult:
        """Archive staging/rejection and audit without changing approved state."""
        return self._transact(deal_id, idempotency_key=idempotency_key, request_payload=request_payload,
                              expected_revision=expected_revision, mutate=mutate, audit_only=True)

    def _transact(self, deal_id: str, *, idempotency_key: str, request_payload: Any,
                  expected_revision: int, mutate: Callable[[RevisionWriter], None],
                  audit_only: bool) -> RepositoryCommitResult:
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("idempotency_key must be a nonempty string")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        digest = payload_digest(request_payload)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            writer = None
            try:
                previous = connection.execute(
                    "SELECT * FROM processed_commands WHERE deal_id=? AND idempotency_key=?",
                    (deal_id, idempotency_key)).fetchone()
                if previous is not None:
                    if previous["request_digest"] != digest:
                        raise RepositoryError("IDEMPOTENCY_CONFLICT", "Key already used for a different payload")
                    connection.commit()
                    return RepositoryCommitResult(previous["result_revision"], previous["snapshot_id"], True)
                head = connection.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
                if head is None:
                    raise RepositoryError("UNKNOWN_DEAL", "Deal is not installed")
                if head["state_revision"] != expected_revision:
                    raise RepositoryError("REVISION_CONFLICT", "Expected revision does not match current state")
                writer_class = AuditWriter if audit_only else RevisionWriter
                writer = writer_class(self, connection, deal_id, expected_revision,
                                      head["head_snapshot_id"], idempotency_key)
                mutate(writer)
                writer._finish()
                if not audit_only:
                    connection.execute("UPDATE deals SET state_revision=?,head_snapshot_id=? WHERE deal_id=?",
                                       (writer.target_revision, writer.head_snapshot_id, deal_id))
                self._validate(_read_state(connection, deal_id))
                connection.execute("INSERT INTO processed_commands VALUES (?,?,?,?,?)",
                                   (deal_id, idempotency_key, digest, writer.target_revision, writer.head_snapshot_id))
                connection.commit()
                return RepositoryCommitResult(writer.target_revision, writer.head_snapshot_id)
            except BaseException:
                connection.rollback()
                raise
            finally:
                if writer is not None:
                    writer._active = False

    def entity_history(self, deal_id: str, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [json.loads(row[0]) for row in connection.execute(
                "SELECT payload FROM entity_versions WHERE deal_id=? AND entity_type=? AND entity_id=? "
                "ORDER BY entity_version", (deal_id, entity_type, entity_id))]


class RevisionWriter:
    """Transaction-scoped trusted service interface; invalid after callback exit."""

    def __init__(self, repo: SQLiteRepository, connection: sqlite3.Connection, deal_id: str,
                 base_revision: int, before_snapshot_id: str | None, idempotency_key: str | None):
        self._repo = repo
        self._connection = connection
        self.deal_id = deal_id
        self.base_revision = base_revision
        self.target_revision = base_revision + 1
        self.before_snapshot_id = before_snapshot_id
        self.idempotency_key = idempotency_key
        self.head_snapshot_id: str | None = None
        self._active = True
        self._new_audits: list[dict[str, Any]] = []
        self._new_decisions: list[dict[str, Any]] = []

    def _check(self) -> None:
        if not self._active:
            raise RepositoryError("TRANSACTION_CLOSED", "Writer may only be used inside its callback")

    def read_state(self) -> DealState:
        self._check()
        return _read_state(self._connection, self.deal_id)

    def archive_staged(self, event: StagedEvidenceUpdate) -> None:
        self._check()
        event = StagedEvidenceUpdate.model_validate(event.model_dump(mode="json"))
        if event.deal_id != self.deal_id:
            raise RepositoryError("CROSS_DEAL_REFERENCE", "Event belongs to another deal")
        if self._connection.execute("SELECT 1 FROM staged_updates WHERE deal_id=? AND event_id=?",
                                    (self.deal_id, event.id)).fetchone():
            raise RepositoryError("DUPLICATE_EVENT", "Staged event IDs are immutable; submit a new event ID")
        self._connection.execute("INSERT INTO staged_updates VALUES (?,?,?,?)",
                                 (self.deal_id, event.id, payload_digest(event), canonical_json(event)))

    def read_staged(self, event_id: str) -> StagedEvidenceUpdate:
        self._check()
        row = self._connection.execute("SELECT payload,payload_digest FROM staged_updates "
                                       "WHERE deal_id=? AND event_id=?", (self.deal_id, event_id)).fetchone()
        if row is None:
            raise RepositoryError("UNKNOWN_EVENT", "Event has not been staged for this deal")
        value = StagedEvidenceUpdate.model_validate_json(row["payload"])
        if payload_digest(value) != row["payload_digest"]:
            raise RepositoryError("SOURCE_MISMATCH", "Staged event archive digest does not match")
        if self._connection.execute("SELECT 1 FROM staged_resolutions WHERE deal_id=? AND event_id=?",
                                    (self.deal_id, event_id)).fetchone():
            raise RepositoryError("DUPLICATE_EVENT", "This event has already been decided")
        return value

    def resolve_staged(self, event_id: str, action: str, decision_id: str) -> None:
        self._check()
        self.read_staged(event_id)
        self._connection.execute("INSERT INTO staged_resolutions VALUES (?,?,?,?)",
                                 (self.deal_id, event_id, action, decision_id))

    def put_source_blob(self, content: bytes, *, expected_sha256: str | None = None) -> str:
        self._check()
        if type(content) is not bytes:
            raise TypeError("Source content must be bytes")
        digest = sha256(content).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise RepositoryError("SOURCE_MISMATCH", "Source bytes do not match declared digest")
        existing = self._connection.execute(
            "SELECT content FROM source_blobs WHERE deal_id=? AND sha256=?", (self.deal_id, digest)).fetchone()
        if existing is None:
            self._connection.execute("INSERT INTO source_blobs VALUES (?,?,?,?)",
                                     (self.deal_id, digest, len(content), content))
        elif existing[0] != content:
            raise RepositoryError("SOURCE_MISMATCH", "Stored source content mismatch")
        return digest

    def put_entity(self, type_name: str, value: Any) -> None:
        self._check()
        data = _as_payload(type_name, value)
        if (data["id"] if type_name == "Deal" else data["deal_id"]) != self.deal_id:
            raise RepositoryError("CROSS_DEAL_REFERENCE", "Entity belongs to another deal")
        current = self._connection.execute(
            "SELECT entity_type,entity_version,payload FROM entity_versions WHERE deal_id=? AND entity_id=? "
            "ORDER BY entity_version DESC LIMIT 1", (self.deal_id, data["id"])).fetchone()
        if current and current["entity_type"] != type_name:
            raise RepositoryError("ENTITY_ID_CONFLICT", "Entity ID is already used by another type")
        if type_name in IMMUTABLE_TYPES and (current or data["entity_version"] != 1):
            raise RepositoryError("IMMUTABLE_ENTITY", "Snapshot, decision and audit entities are append-only")
        expected_version = current["entity_version"] + 1 if current else 1
        if data["entity_version"] != expected_version:
            raise RepositoryError("ENTITY_VERSION_CONFLICT", "Entity versions must increase by exactly one")
        if type_name in {"Document", "Evidence"} and current:
            if json.loads(current["payload"])["created_at"] != data["created_at"]:
                raise RepositoryError("IMMUTABLE_METADATA", "Original entity creation time cannot change")
        if type_name == "Document" and current:
            old = json.loads(current["payload"])
            content_changed = any(old[k] != data[k] for k in ("file_sha256", "parser_version", "format", "asset_status"))
            required = old["document_version"] + int(content_changed)
            if data["document_version"] != required:
                raise RepositoryError("DOCUMENT_VERSION_CONFLICT", "Source/parser change requires exactly one new document version")
        if type_name == "SourceSpan" and current:
            old = json.loads(current["payload"])
            immutable_source_fields = ("document_id", "document_version", "locator", "normalized_text", "text_sha256")
            if any(old[k] != data[k] for k in immutable_source_fields):
                raise RepositoryError("SOURCE_VERSION_CONFLICT", "Changed extraction units require a new SourceSpan ID")
        if type_name == "RankingSnapshot" and data["state_revision"] != self.target_revision:
            raise RepositoryError("SNAPSHOT_REVISION_CONFLICT", "Snapshot must belong to the transaction revision")
        if type_name == "AuditEvent":
            self._validate_audit(data)
        if type_name == "AnalystDecision" and data["base_revision"] != self.base_revision:
            raise RepositoryError("REVISION_CONFLICT", "Decision is not bound to the current base revision")
        payload = canonical_json(data)
        source_hash = data["file_sha256"] if type_name == "Document" else None
        self._connection.execute("INSERT INTO entity_versions VALUES (?,?,?,?,?,?)",
                                 (self.deal_id, type_name, data["id"], data["entity_version"], source_hash, payload))
        if type_name == "RankingSnapshot":
            self._connection.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?)",
                (self.deal_id, data["id"], type_name, 1, data["state_revision"], payload))
        elif type_name == "AnalystDecision":
            self._connection.execute("INSERT INTO decisions VALUES (?,?,?,?,?)",
                (self.deal_id, data["id"], type_name, 1, payload))
            self._new_decisions.append(data)
        elif type_name == "AuditEvent":
            self._connection.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.deal_id, data["id"], type_name, 1, data["sequence"], data["decision_id"],
                 data["before_snapshot_id"], data["after_snapshot_id"], data["event_hash"], payload))
            self._new_audits.append(data)
        elif type_name == "AnalysisRun":
            self._connection.execute("INSERT INTO analysis_runs VALUES (?,?,?,?,?)",
                (self.deal_id, data["id"], type_name, data["entity_version"], payload))

    def append_snapshot(self, value: Any) -> None:
        self.put_entity("RankingSnapshot", value)

    def append_decision(self, value: Any) -> None:
        self.put_entity("AnalystDecision", value)

    def append_audit(self, value: Any) -> None:
        self.put_entity("AuditEvent", value)

    def _validate_audit(self, data: dict[str, Any]) -> None:
        previous = self._connection.execute("SELECT sequence,event_hash,payload FROM audit_events "
                                           "WHERE deal_id=? ORDER BY sequence DESC LIMIT 1", (self.deal_id,)).fetchone()
        expected_sequence = previous["sequence"] + 1 if previous else 1
        expected_hash = previous["event_hash"] if previous else None
        if data["sequence"] != expected_sequence or data["previous_hash"] != expected_hash:
            raise RepositoryError("AUDIT_CHAIN_INVALID", "Audit sequence or previous hash is invalid")
        unsigned = {k: v for k, v in data.items() if k != "event_hash"}
        if payload_digest(unsigned) != data["event_hash"]:
            raise RepositoryError("AUDIT_HASH_INVALID", "Audit content does not match event hash")
        if not self.base_revision <= data["before_revision"] <= data["after_revision"] <= self.target_revision:
            raise RepositoryError("REVISION_CONFLICT", "Audit revisions are not within this transaction")
        if previous and json.loads(previous["payload"])["after_revision"] > data["before_revision"]:
            raise RepositoryError("AUDIT_CHAIN_INVALID", "Audit revisions cannot move backward")
        if self.idempotency_key is not None and data["idempotency_key"] != self.idempotency_key:
            raise RepositoryError("IDEMPOTENCY_CONFLICT", "Audit is not bound to this command")

    def set_head(self, snapshot_id: str) -> None:
        self._check()
        row = self._connection.execute("SELECT state_revision FROM snapshots WHERE deal_id=? AND snapshot_id=?",
                                       (self.deal_id, snapshot_id)).fetchone()
        if row is None or row[0] != self.target_revision:
            raise RepositoryError("HEAD_SNAPSHOT_MISMATCH", "Head must be this transaction's new snapshot")
        self.head_snapshot_id = snapshot_id

    def _finish(self) -> None:
        if self.head_snapshot_id is None:
            raise RepositoryError("INCOMPLETE_COMMIT", "Transaction must append and select a new snapshot")
        decision_ids = {item["id"] for item in self._new_decisions}
        if not any(item["after_revision"] == self.target_revision
                   and item["before_revision"] == self.base_revision
                   and item["before_snapshot_id"] == self.before_snapshot_id
                   and item["after_snapshot_id"] == self.head_snapshot_id
                   and item["decision_id"] in decision_ids for item in self._new_audits):
            raise RepositoryError("INCOMPLETE_COMMIT", "Transaction requires a new decision and linked revision audit")


class AuditWriter(RevisionWriter):
    """Only immutable audit/decision/archive writes are permitted in this path."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.target_revision = self.base_revision
        self.head_snapshot_id = self.before_snapshot_id

    def put_entity(self, type_name: str, value: Any) -> None:
        if type_name not in {"AnalystDecision", "AuditEvent"}:
            raise RepositoryError("AUDIT_ONLY_MUTATION", "Staging/rejection cannot modify ranking entities")
        super().put_entity(type_name, value)

    def set_head(self, snapshot_id: str) -> None:
        raise RepositoryError("AUDIT_ONLY_MUTATION", "Staging/rejection cannot change the snapshot")

    def _finish(self) -> None:
        if not self._new_audits:
            raise RepositoryError("INCOMPLETE_COMMIT", "Audit-only command requires an audit event")
        decisions = {item["id"]: item for item in self._new_decisions}
        for audit in self._new_audits:
            if (audit["before_revision"] != self.base_revision or audit["after_revision"] != self.base_revision
                    or audit["before_snapshot_id"] != self.before_snapshot_id
                    or audit["after_snapshot_id"] != self.before_snapshot_id
                    or audit["event_type"] not in {"update_staged", "update_rejected"}):
                raise RepositoryError("INCOMPLETE_COMMIT", "Audit-only command must preserve revision and head")
            if audit["event_type"] == "update_rejected":
                decision = decisions.get(audit["decision_id"])
                if decision is None or decision["action"] != "reject":
                    raise RepositoryError("INCOMPLETE_COMMIT", "Rejection requires its new reviewer decision")


def _read_state(connection: sqlite3.Connection, deal_id: str) -> DealState:
    head = connection.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    if head is None:
        raise RepositoryError("UNKNOWN_DEAL", "Deal is not installed")
    result: dict[str, Any] = {
        "kind": "deal_state", "contract_version": head["contract_version"], "mode": head["mode"],
        "state_revision": head["state_revision"], "head_snapshot_id": head["head_snapshot_id"],
        **{name: [] for name in COLLECTIONS.values()},
    }
    rows = connection.execute("SELECT e.entity_type,e.payload FROM entity_versions e JOIN "
        "(SELECT entity_type,entity_id,MAX(entity_version) AS version FROM entity_versions "
        "WHERE deal_id=? GROUP BY entity_type,entity_id) latest "
        "ON e.entity_type=latest.entity_type AND e.entity_id=latest.entity_id AND e.entity_version=latest.version "
        "WHERE e.deal_id=? ORDER BY e.entity_type,e.entity_id", (deal_id, deal_id))
    for row in rows:
        payload = json.loads(row["payload"])
        if row["entity_type"] == "Deal":
            result["deal"] = payload
        else:
            result[COLLECTIONS[row["entity_type"]]].append(payload)
    result["audit_events"].sort(key=lambda item: item["sequence"])
    result["ranking_snapshots"].sort(key=lambda item: item["state_revision"])
    return DealState.model_validate(result)
