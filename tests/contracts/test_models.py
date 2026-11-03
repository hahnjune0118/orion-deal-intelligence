"""Independent JSON Schema oracle against actual strict Pydantic validation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import TypeAdapter, ValidationError
import pytest

from orion.domain.models import (ENTITY_MODELS, MODEL_TYPES, AnalysisRun, Deal,
                                 Document, Evidence, AnalystDecision,
                                 envelope_json_schema, validate_envelope)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'spec/SCHEMAS/models.schema.json').read_text())
ORACLE = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
FIXTURES = sorted(
    p for directory in ('EXAMPLES', 'DATASET_SPECS/cd', 'DATASET_SPECS/lm')
    for p in (ROOT / 'spec' / directory).glob('*.json')
)


def sample(schema):
    """Small schema-only specimen; never uses generated model metadata."""
    if '$ref' in schema:
        return sample(SCHEMA['$defs'][schema['$ref'].rsplit('/', 1)[-1]])
    if 'const' in schema:
        return schema['const']
    if 'enum' in schema:
        return schema['enum'][0]
    if 'anyOf' in schema:
        return sample(schema['anyOf'][0])
    if 'oneOf' in schema:
        return sample(schema['oneOf'][0])
    kind = schema['type']
    if kind == 'object':
        value = {key: sample(prop) for key, prop in schema['properties'].items()}
        if 'selection_digest' in value:
            value['selection_digest'] = None  # non-export conditional
        return value
    if kind == 'array':
        return [sample(schema['items']) for _ in range(schema.get('minItems', 0))]
    if kind == 'null':
        return None
    if kind == 'boolean':
        return False
    if kind in ('integer', 'number'):
        return schema.get('minimum', 0)
    if schema.get('format') == 'date':
        return '2026-11-03'
    if schema.get('format') == 'date-time':
        return '2026-11-03T00:00:00Z'
    if schema.get('pattern') == '^[a-f0-9]{64}$':
        return 'a' * 64
    return 'sample'


def oracle_for(name):
    return Draft202012Validator({'$ref': f'#/$defs/{name}', '$defs': SCHEMA['$defs']},
                               format_checker=FormatChecker())


def accepted_by_model(name, value):
    try:
        MODEL_TYPES[name].model_validate(value)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize('path', FIXTURES, ids=lambda p: str(p.relative_to(ROOT / 'spec')))
def test_nine_envelopes_pass_schema_and_model_without_rewriting(path):
    original = json.loads(path.read_text())
    ORACLE.validate(original)
    actual = validate_envelope(original).model_dump(mode='json')
    # Compare serialization, not just Python numeric equality (1 != 1.0 in digests).
    assert json.dumps(actual, ensure_ascii=False, sort_keys=True) == json.dumps(original, ensure_ascii=False, sort_keys=True)
    assert validate_envelope(path.read_bytes()).model_dump(mode='json') == actual


def test_exactly_nine_supplied_envelopes():
    assert len(FIXTURES) == 9
    assert len(ENTITY_MODELS) == 12


@pytest.mark.parametrize('name', sorted(MODEL_TYPES))
def test_every_object_definition_accepts_independent_schema_specimen(name):
    value = sample(SCHEMA['$defs'][name])
    oracle_for(name).validate(value)
    actual = MODEL_TYPES[name].model_validate(value).model_dump(mode='json')
    assert actual == value


def structural_mutations():
    for name, schema in SCHEMA['$defs'].items():
        if 'properties' not in schema:
            continue
        base = sample(schema)
        unknown = deepcopy(base)
        unknown['unrecognized'] = 'reject'
        yield pytest.param(name, unknown, id=f'{name}-unknown-field')
        for field, prop in schema['properties'].items():
            missing = deepcopy(base)
            del missing[field]
            yield pytest.param(name, missing, id=f'{name}-{field}-required')
        # Domain-sensitive rejection corpus, independently checked against schema.
        for field in ('id', 'deal_id', 'document_id', 'question_id'):
            if field in base:
                wrong = deepcopy(base)
                wrong[field] = 'Uppercase_invalid'
                yield pytest.param(name, wrong, id=f'{name}-{field}-invalid-id')
        for field, prop in schema['properties'].items():
            if 'enum' in prop:
                wrong = deepcopy(base)
                wrong[field] = 'unknown_enum'
                yield pytest.param(name, wrong, id=f'{name}-{field}-invalid-enum')
            if prop.get('format'):
                wrong = deepcopy(base)
                wrong[field] = '2026-02-30' if prop['format'] == 'date' else '2026-11-03T00:00:00+09:00'
                yield pytest.param(name, wrong, id=f'{name}-{field}-invalid-date')
            if prop.get('type') == 'integer':
                wrong = deepcopy(base)
                wrong[field] = str(base[field])
                yield pytest.param(name, wrong, id=f'{name}-{field}-string-number')
            if prop.get('uniqueItems'):
                wrong = deepcopy(base)
                wrong[field] = [sample(prop['items'])] * 2
                yield pytest.param(name, wrong, id=f'{name}-{field}-duplicate-items')
            if prop.get('type') == 'string' and prop.get('minLength') == 1:
                wrong = deepcopy(base)
                wrong[field] = ''
                yield pytest.param(name, wrong, id=f'{name}-{field}-empty')


@pytest.mark.parametrize('name,value', structural_mutations())
def test_structural_rejection_parity(name, value):
    assert not oracle_for(name).is_valid(value)
    assert not accepted_by_model(name, value)


def expanded_semantics(node, definitions):
    """Ignore annotation-only differences, inline refs without weakening rules."""
    if isinstance(node, list):
        return [expanded_semantics(v, definitions) for v in node]
    if not isinstance(node, dict):
        return node
    if '$ref' in node:
        return expanded_semantics(definitions[node['$ref'].rsplit('/', 1)[-1]], definitions)
    result = {k: expanded_semantics(v, definitions) for k, v in node.items()
              if k not in {'title', 'description', 'discriminator', '$defs', '$id', '$schema'}}
    # Literal type annotations are redundant; const already determines JSON type.
    if 'const' in result:
        result.pop('type', None)
    return result


@pytest.mark.parametrize('name', sorted(MODEL_TYPES))
def test_generated_schema_semantics_match_source_after_metadata_normalization(name):
    generated = MODEL_TYPES[name].model_json_schema()
    definitions = generated.get('$defs', {})
    assert expanded_semantics(generated, definitions) == expanded_semantics(SCHEMA['$defs'][name], SCHEMA['$defs'])


def test_envelope_and_locator_discriminators_match_source_semantics():
    generated = envelope_json_schema()
    assert expanded_semantics(generated, generated['$defs']) == expanded_semantics(SCHEMA, SCHEMA['$defs'])


@pytest.mark.parametrize('name,updates', [
    ('Document', {'asset_status': 'file_verified', 'file_sha256': None}),
    ('Evidence', {'verification_level': 'independent_check', 'independent_check_reference': None}),
    ('DDQuestion', {'workflow_status': 'duplicate', 'duplicate_of': None}),
    ('AnalystDecision', {'target_type': 'snapshot_export', 'selection_digest': None}),
    ('AnalystDecision', {'target_type': 'evidence', 'selection_digest': 'a' * 64}),
    ('AnalysisRun', {'mode': 'cached', 'token_input': 1}),
    ('AnalysisRun', {'mode': 'cached', 'token_output': None}),
    ('AnalysisRun', {'mode': 'cached', 'reserved_cost_usd': 0.01}),
    ('AnalysisRun', {'mode': 'cached', 'actual_cost_usd': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'model_id': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'pricing_version': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'token_input': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'token_output': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'finished_at': None}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed', 'actual_cost_usd': None}),
])
def test_conditional_schema_rejection_parity(name, updates):
    value = sample(SCHEMA['$defs'][name])
    value.update(updates)
    assert not oracle_for(name).is_valid(value)
    assert not accepted_by_model(name, value)


@pytest.mark.parametrize('name,updates', [
    ('Document', {'asset_status': 'file_verified', 'file_sha256': 'a' * 64}),
    ('Evidence', {'verification_level': 'independent_check', 'independent_check_reference': 'verified reference'}),
    ('DDQuestion', {'workflow_status': 'duplicate', 'duplicate_of': 'other_question'}),
    ('AnalystDecision', {'target_type': 'snapshot_export', 'selection_digest': 'a' * 64}),
    ('AnalysisRun', {'mode': 'live', 'status': 'completed'}),
])
def test_conditional_schema_acceptance_parity(name, updates):
    value = sample(SCHEMA['$defs'][name])
    value.update(updates)
    oracle_for(name).validate(value)
    MODEL_TYPES[name].model_validate(value)


@pytest.mark.parametrize('value', [True, '1', 1.0])
def test_strict_integer_policy_has_no_type_coercion(value):
    specimen = sample(SCHEMA['$defs']['Deal'])
    specimen['entity_version'] = value
    with pytest.raises(ValidationError):
        Deal.model_validate(specimen)
    # JSON Schema regards 1.0 as an integer. The prose explicitly adds strict
    # no-coercion policy; this is documented, not misrepresented as metadata.
    assert oracle_for('Deal').is_valid(specimen) is (type(value) is float)


@pytest.mark.parametrize('value', [1, 1.0, 'true', False])
def test_synthetic_literal_is_a_real_boolean(value):
    specimen = sample(SCHEMA['$defs']['Deal'])
    specimen['synthetic'] = value
    assert not oracle_for('Deal').is_valid(specimen)
    with pytest.raises(ValidationError):
        Deal.model_validate(specimen)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), True, '1.25'])
def test_numbers_are_finite_json_numbers_only(value):
    specimen = sample(SCHEMA['$defs']['TransitionRow'])
    specimen['before_score'] = value
    with pytest.raises(ValidationError):
        MODEL_TYPES['TransitionRow'].model_validate(specimen)


@pytest.mark.parametrize('value', ['2026-1-03', '2026-02-30', '2026-11-03T00:00:00Z', ''])
def test_date_calendar_validation(value):
    specimen = sample(SCHEMA['$defs']['Deal'])
    specimen['as_of'] = value
    with pytest.raises(ValidationError):
        Deal.model_validate(specimen)


@pytest.mark.parametrize('value', ['2026-02-30T00:00:00Z', '2026-11-03T25:00:00Z', '2026-11-03T00:00:00+00:00', '2026-11-03T00:00:00z'])
def test_utc_timestamp_validation(value):
    specimen = sample(SCHEMA['$defs']['Document'])
    specimen['created_at'] = value
    with pytest.raises(ValidationError):
        Document.model_validate(specimen)


def test_json_duplicate_keys_and_nonfinite_constants_are_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        validate_envelope('{"kind":"deal_state","kind":"expected_top3_transition"}')
    with pytest.raises(ValueError, match='non-finite'):
        validate_envelope('{"state_revision":NaN}')


def test_no_automatic_truth_or_review_promotion():
    original = json.loads(FIXTURES[0].read_text())
    parsed = validate_envelope(original)
    assert parsed.model_dump(mode='json') == original
