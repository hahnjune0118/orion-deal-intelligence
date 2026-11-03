from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from orion.domain.grounding import (
    GroundingError, canonical_hash, input_digest, normalize_text, split_quote,
    text_sha256, validate_expected_transition, validate_grounding,
)
from orion.adapters.parsers.base import NativeParserUnavailable

ROOT = Path(__file__).resolve().parents[2]
CASES = [ROOT / "spec/EXAMPLES", ROOT / "spec/DATASET_SPECS/cd", ROOT / "spec/DATASET_SPECS/lm"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def state():
    return read(CASES[0] / "initial_state.json")


@pytest.fixture
def update():
    return read(CASES[0] / "staged_evidence_update.json")


@pytest.mark.parametrize("case", CASES, ids=["northstar", "cedar", "lumen"])
def test_all_fixture_reference_sets(case):
    base = read(case / "initial_state.json")
    staged = read(case / "staged_evidence_update.json")
    expected = read(case / "expected_top3_transition.json")
    before = deepcopy((base, staged))
    report = validate_grounding(base)
    assert input_digest(base) == base["ranking_snapshots"][0]["input_digest"]
    report.raise_for_errors()
    assert report.fixture_text_only
    validate_grounding(base, staged).raise_for_errors()
    validate_expected_transition(base, staged, expected).raise_for_errors()
    assert (base, staged) == before  # Source approval never mutates stored status.


@pytest.mark.parametrize("mutate", [
    lambda s: s["source_spans"][0].update(quote="invented"),
    lambda s: s["source_spans"][0].update(start=1),
    lambda s: s["source_spans"][0].update(end=10**8),
    lambda s: s["source_spans"][0].update(text_sha256="0"*64),
    lambda s: s["source_spans"][0].update(document_id="doc_unknown"),
    lambda s: s["source_spans"][0].update(document_version=2),
    lambda s: s["source_spans"][0].update(locator={"kind":"pptx","slide":1,"shape_id":1,"paragraph_index":0,"table_cell":None}),
    lambda s: s["source_spans"][0].update(locator_status="unverified"),
    lambda s: s["documents"][0].update(parse_status="needs_ocr"),
    lambda s: s["documents"][0].update(asset_status="file_verified",file_sha256="0"*64),
    lambda s: s["documents"][0].update(file_sha256="0"*64),
    lambda s: s["source_spans"][0].update(extraction_method="parsed"),
])
def test_bad_citations_cannot_validate(state, mutate):
    mutate(state)
    report = validate_grounding(state)
    assert not report.valid
    with pytest.raises(GroundingError):
        report.raise_for_errors()


@pytest.mark.parametrize("mutate", [
    lambda s: s["documents"][0].update(deal_id="deal_else"),
    lambda s: s["evidence"][0].update(claim_id="claim_unknown"),
    lambda s: s["evidence"][0].update(source_span_ids=["span_unknown"]),
    lambda s: s["claims"][0].update(thesis_id="thesis_unknown"),
    lambda s: s["theses"][0].update(claim_ids=["claim_ns"]),
    lambda s: s["claims"][0].update(period_end="2025-01-01"),
    lambda s: s["dd_questions"][0]["requirements"][0].update(key="unrelated"),
    lambda s: s["evidence"][0].update(criterion_keys=["unrelated"]),
    lambda s: s["dd_questions"][0]["requirements"].append(deepcopy(s["dd_questions"][0]["requirements"][0])),
    lambda s: s["claims"][0].update(truth_status="independently_verified"),
    lambda s: s["evidence"][0].update(verification_level="independent_check"),
    lambda s: s["claims"][0].update(claim_kind="analyst_assumption"),
    lambda s: s["dd_questions"][0].update(duplicate_of="q_ns_contract_b"),
    lambda s: s["documents"][0].update(id="claim_ns"),
])
def test_reference_and_truth_guards(state, mutate):
    mutate(state)
    assert not validate_grounding(state).valid


def test_shared_policy_consistency(state):
    second = state["dd_questions"][1]
    second["requirements"].append({"key":"contract_a","label":"A", "min_reliability":4,"require_independent":False})
    assert not validate_grounding(state).valid


def test_fixture_mode_cannot_be_live(state):
    assert not validate_grounding(state, mode="local_live").valid
    state["mode"] = "local_live"
    assert not validate_grounding(state, mode="contract").valid
    assert not validate_grounding(state, mode="demo").valid


def test_staged_cross_deal_stale_unknown_claim(state, update):
    for key, value in [("deal_id", "deal_else"), ("base_revision", 2)]:
        changed = deepcopy(update)
        changed[key] = value
        assert not validate_grounding(state, changed).valid
    update["evidence"][0]["claim_id"] = "claim_else"
    assert not validate_grounding(state, update).valid


def test_staged_duplicate_id_and_version(state, update):
    update["evidence"][0]["id"] = state["evidence"][0]["id"]
    assert not validate_grounding(state, update).valid
    update["evidence"][0]["entity_version"] = 2
    assert validate_grounding(state, update).valid


def test_unicode_offsets_and_normalization():
    assert normalize_text(b"a\r\nb\rc") == "a\nb\nc"
    assert normalize_text("e\u0301  X-\nY") == "é  X-\nY"
    assert normalize_text("A  B") != normalize_text("A B")
    assert text_sha256("e\u0301\r\n") == hashlib.sha256("é\n".encode()).hexdigest()
    with pytest.raises(UnicodeDecodeError):
        normalize_text(b"\xff")
    span = {"normalized_text":"x😀quote quote", "start":2, "end":7, "quote":"quote"}
    assert split_quote(span) == ("x😀", "quote", " quote")
    span["start"] = 3  # JavaScript UTF-16 coordinate must not be used directly.
    with pytest.raises(GroundingError):
        split_quote(span)


class Resolver:
    def __init__(self, raw, units):
        self.raw, self.units = raw, units
    def file_bytes(self, document):
        return self.raw
    def resolve_units(self, document, locator):
        return self.units


def verified_state(state):
    raw = b"server-owned original bytes"
    state["documents"][0].update(asset_status="file_verified",file_sha256=hashlib.sha256(raw).hexdigest())
    state["source_spans"][0]["extraction_method"] = "parsed"
    return raw, state["source_spans"][0]["normalized_text"]


def test_file_verified_requires_independent_source_resolution(state):
    raw, text = verified_state(state)
    report = validate_grounding(state, mode="local_live", source_resolver=Resolver(raw,[text]))
    assert report.valid and not report.fixture_text_only
    assert state["claims"][0]["truth_status"] == "document_only"
    assert not validate_grounding(state, source_resolver=Resolver(b"tampered",[text])).valid
    assert not validate_grounding(state, source_resolver=Resolver(raw,[])).valid
    assert not validate_grounding(state, source_resolver=Resolver(raw,[text,text])).valid
    assert not validate_grounding(state, source_resolver=Resolver(raw,[text+" x"])).valid


def test_forged_text_and_hash_cannot_defeat_external_resolver(state):
    raw, original = verified_state(state)
    span = state["source_spans"][0]
    span.update(normalized_text="Forged exact quote", quote="Forged exact quote",start=0,end=18,text_sha256=text_sha256("Forged exact quote"))
    assert not validate_grounding(state, source_resolver=Resolver(raw,[original])).valid


def test_conflicting_fixture_units_rejected(state):
    span = deepcopy(state["source_spans"][0])
    span.update(id="span_other",normalized_text="Another",quote="Another",start=0,end=7,text_sha256=text_sha256("Another"))
    state["source_spans"].append(span)
    assert not validate_grounding(state).valid


def test_native_docx_locator_rejects_fabricated_page(state, update):
    update["source_spans"][0]["locator"]["page"] = 2
    assert not validate_grounding(state,update).valid
    del update["source_spans"][0]["locator"]["page"]
    update["source_spans"][0]["locator"]["paragraph_index"] = 1
    assert not validate_grounding(state,update).valid


@pytest.mark.parametrize("mutate", [
    lambda s: s["ranking_snapshots"][0]["rows"][0].update(rank=2),
    lambda s: s["ranking_snapshots"][0].update(top3=[]),
    lambda s: s.update(state_revision=2),
    lambda s: s["audit_events"][0].update(event_hash="0"*64),
    lambda s: s["audit_events"][0].update(previous_hash="0"*64),
    lambda s: s["audit_events"][0].update(sequence=2),
    lambda s: s["analyst_decisions"][0].update(target_id="deal_unknown"),
    lambda s: s["analyst_decisions"][0].update(actor_role="analyst"),
    lambda s: s["analysis_runs"][0].update(actual_cost_usd=1),
])
def test_snapshot_audit_decision_run_guards(state, mutate):
    mutate(state)
    assert not validate_grounding(state).valid


def test_recorded_input_bins(state):
    q = state["dd_questions"][0]
    q["materiality"].update(basis="objective_ratio",exposure_minor=2000,denominator_minor=10000,source_span_ids=[state["source_spans"][0]["id"]],score=5)
    q["obtainability"].update(basis="derived_cost_time", days=2, external_cost_minor=60000,score=2)
    assert validate_grounding(state).valid
    q["materiality"]["score"] = 4
    assert not validate_grounding(state).valid
    q["materiality"]["score"] = 5
    q["obtainability"]["score"] = 4
    assert not validate_grounding(state).valid
    q["obtainability"]["score"] = 2
    q["materiality"]["denominator_minor"] = 0
    assert not validate_grounding(state).valid


def test_unknown_inputs_require_null(state):
    state["dd_questions"][0]["materiality"].update(basis="unknown",score=0)
    assert not validate_grounding(state).valid
    state["dd_questions"][0]["materiality"]["score"] = None
    assert validate_grounding(state).valid


def relation_state(state):
    old = state["evidence"][0]
    old.update(stance="supports",criterion_keys=["contract_a"])
    new = deepcopy(old)
    new.update(id="ev_new",origin_key="new")
    state["evidence"].append(new)
    relation = {"id":"rel_001","entity_version":1,"deal_id":state["deal"]["id"],"from_evidence_id":new["id"],"to_evidence_id":old["id"],"relation_type":"supersedes","scope_criterion_keys":["contract_a"],"review_status":"approved","rationale":"Full approved replacement"}
    state["evidence_relations"] = [relation]
    return old,new,relation


def test_supersedes_full_scope_and_cycle(state):
    old,new,relation = relation_state(state)
    assert not validate_grounding(state).valid
    old["lifecycle"] = "superseded"
    assert validate_grounding(state).valid
    new["review_status"] = "draft"
    assert not validate_grounding(state).valid
    new["review_status"] = "approved"
    back = deepcopy(relation)
    back.update(id="rel_002",from_evidence_id=old["id"],to_evidence_id=new["id"])
    new["lifecycle"] = "superseded"
    state["evidence_relations"].append(back)
    assert not validate_grounding(state).valid


def test_opposing_evidence_is_not_duplicate(state):
    old,new,relation = relation_state(state)
    relation["relation_type"] = "duplicates"
    assert validate_grounding(state).valid
    new["stance"] = "refutes"
    assert not validate_grounding(state).valid


def test_digest_stable_and_ordered_inner_lists_preserved(state):
    expected = input_digest(state)
    state["dd_questions"].reverse()
    assert input_digest(state) == expected
    state["claims"][0]["required_criterion_keys"].reverse()
    assert input_digest(state) != expected
    assert canonical_hash({"b":1,"a":"한"}) == canonical_hash({"a":"한","b":1})
    with pytest.raises(ValueError):
        canonical_hash({"n":float("nan")})


def test_parser_boundary_is_explicitly_unimplemented():
    with pytest.raises(NotImplementedError, match="Chunk 1"):
        NativeParserUnavailable().parse_document(b"file", {})


def test_report_does_not_leak_source_on_resolver_failure(state):
    raw,_ = verified_state(state)
    class Broken(Resolver):
        def file_bytes(self, document):
            raise ValueError("secret-private-source")
    report = validate_grounding(state,source_resolver=Broken(raw,[]))
    assert not report.valid
    with pytest.raises(GroundingError) as exc:
        report.raise_for_errors()
    assert "secret-private-source" not in str(exc.value)


def test_run_timestamp_comparison_uses_time_not_lexical_order(state):
    run = state["analysis_runs"][0]
    run["started_at"] = "2026-11-03T00:00:00Z"
    run["finished_at"] = "2026-11-03T00:00:00.500Z"
    assert validate_grounding(state).valid
    run["started_at"] = "2026-11-03T00:00:00.600Z"
    assert not validate_grounding(state).valid


@pytest.mark.parametrize("field", ["materiality", "obtainability"])
def test_known_analyst_inputs_need_score(state, field):
    state["dd_questions"][0][field]["score"] = None
    assert not validate_grounding(state).valid


def test_independent_truth_cannot_hide_approved_active_refutation(state):
    claim = state["claims"][0]
    ev = state["evidence"][0]
    ev.update(stance="supports",criterion_keys=list(claim["required_criterion_keys"]),verification_level="independent_check",independent_check_reference="Synthetic independent confirmation")
    decision = deepcopy(state["analyst_decisions"][0])
    decision.update(id="decision_claim",target_type="claim",target_id=claim["id"],target_version=claim["entity_version"],base_revision=1)
    state["analyst_decisions"].append(decision)
    claim["truth_status"] = "independently_verified"
    assert validate_grounding(state).valid
    refute = deepcopy(ev)
    refute.update(id="ev_refute",stance="refutes",criterion_keys=[claim["required_criterion_keys"][0]],verification_level="document_only",independent_check_reference=None)
    state["evidence"].append(refute)
    assert not validate_grounding(state).valid


@pytest.mark.parametrize("collection", ["documents", "evidence"])
def test_staged_update_cannot_rewrite_creation_metadata(state, update, collection):
    changed = deepcopy(state[collection][0])
    changed["entity_version"] += 1
    changed["created_at"] = "2026-11-04T00:00:00Z"
    update[collection].append(changed)
    assert not validate_grounding(state, update).valid


def test_staged_entity_cannot_use_its_envelope_id(state, update):
    update["evidence"][0]["id"] = update["id"]
    assert not validate_grounding(state, update).valid
