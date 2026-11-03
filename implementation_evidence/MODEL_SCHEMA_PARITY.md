# Structural model and schema parity — Chunk 1

The immutable contract remains `1.0.0`. No schema, example, expected outcome,
scoring formula or state transition was edited.

`src/orion/domain/models.py` provides all 24 named object definitions, the four-way
`Locator` union and three-way `Envelope` union. Two inline object definitions are
named for Python typing. The 12 persisted entities are available in
`ENTITY_MODELS`. All fields remain required, including nullable fields; unknown
fields, invalid enum values and non-finite numbers are rejected.

A small standard-library generator writes explicit classes to the repository.
It is not invoked at application startup and does not import `spec/` at runtime.
Cross-record relations, citation integrity, analyst authority and state-derived
semantics are intentionally delegated to their respective domain/services.

The actual test log is `logs/models-pytest.log`. It includes all nine supplied
envelopes; schema-backed positive and negative cases for every named object;
all conditional constraints; strict dates, UTC timestamps and types; canonical
JSON round trips; and generated-schema structural comparison.

## Schema differences

- Descriptive metadata: Pydantic adds titles, discriminators and names for inline
  objects. Reference inlining, metadata removal and removal of redundant `type`
  next to `const` makes the complete generated structural schema equal to the
  supplied schema. Conditional `allOf` clauses and `uniqueItems` are preserved
  in generated schema **and** enforced by Python validators.
- Deliberate stricter input representation required by `04_DATA_CONTRACTS.md`:
  JSON Schema mathematically treats `1.0` as an integer, but strict Pydantic
  integer fields reject the floating-point representation. The zero API-call
  constant likewise requires an actual integer. These are tested semantic
  differences, not hidden as descriptive metadata differences.
- NaN and infinity are forbidden by the prose contract and strict JSON loader;
  permissive Python `json.loads` or a standalone JSON Schema checker is not the
  product input boundary. Duplicate JSON object keys are rejected as ambiguous
  input instead of silently retaining the last value.
- JSON number fields retain the input's integer/float representation. Date and
  UTC timestamp strings retain their original content. This prevents validation
  from silently changing canonical hashes (for example `3` into `3.0`).

This is structural validation evidence, not a measured citation-accuracy,
Top-3-quality, truthfulness, native-parser or application-acceptance result.
