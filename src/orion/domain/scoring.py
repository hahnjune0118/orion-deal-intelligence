"""Deterministic, UI-independent priority rules for scoring contract 1.0.0.

Credit belongs to a requirement, never to a document count. Decimal values are
kept through ordering; JSON numbers are produced only at the contract boundary.
Source matching establishes provenance, not independent truth verification.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from typing import Any

from .grounding import SourceResolver, ValidationMode, input_digest, validate_grounding
from .models import DealState, Evidence, RankingSnapshot, Requirement, ScoreRow

SCORING_VERSION = "1.0.0"
_PRECISION = 50


@dataclass(frozen=True)
class RequirementResult:
    credited_keys: frozenset[str]
    conflict_keys: frozenset[str]
    supporting_evidence_ids: tuple[str, ...]
    refuting_evidence_ids: tuple[str, ...]
    total: int

    @property
    def gap(self) -> Decimal:
        if self.total < 1:
            raise ValueError("At least one requirement is required")
        if self.conflict_keys:
            return Decimal(5)
        with localcontext(Context(prec=_PRECISION)):
            return Decimal(5 * (self.total - len(self.credited_keys))) / self.total

    @property
    def resolved(self) -> bool:
        return self.total > 0 and len(self.credited_keys) == self.total and not self.conflict_keys


def _state(value: DealState | Mapping[str, Any]) -> DealState:
    # Revalidation rejects forged model_construct objects and nested mutations.
    raw = value.model_dump(mode="json") if isinstance(value, DealState) else value
    return DealState.model_validate(raw)


def active_evidence(state: DealState) -> tuple[Evidence, ...]:
    """Approved active atoms with validated, parsed source references.

    Full quote/hash/native-unit checking belongs to validate_grounding, invoked
    by rank_state and the review boundary. This helper also fails closed for an
    unvalidated span when used during derivation of a validated staged update.
    """
    documents = {document.id: document for document in state.documents}
    spans = {span.id: span for span in state.source_spans}

    def usable(atom: Evidence) -> bool:
        if atom.review_status != "approved" or atom.lifecycle != "active":
            return False
        for span_id in atom.source_span_ids:
            span = spans.get(span_id)
            document = documents.get(span.document_id) if span else None
            if not span or not document or span.locator_status != "validated":
                return False
            if document.parse_status != "parsed" or span.document_version != document.document_version:
                return False
            if atom.deal_id != state.deal.id or span.deal_id != state.deal.id or document.deal_id != state.deal.id:
                return False
        return bool(atom.source_span_ids)

    return tuple(sorted((atom for atom in state.evidence if usable(atom)), key=lambda atom: atom.id))


def canonical_origins(state: DealState) -> dict[str, str]:
    """Union approved duplicate origins; never merge opposing claim atoms.

    Requirement credit is boolean even without a duplicate relation. This map
    additionally lets explanation consumers avoid treating relayed copies as
    independent observations. Separate claim atoms may share an origin token.
    """
    atoms = {atom.id: atom for atom in active_evidence(state)}
    parents = {atom.origin_key: atom.origin_key for atom in atoms.values()}

    def root(value: str) -> str:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    for relation in sorted(state.evidence_relations, key=lambda item: item.id):
        if relation.review_status != "approved" or relation.relation_type != "duplicates":
            continue
        left, right = atoms.get(relation.from_evidence_id), atoms.get(relation.to_evidence_id)
        if not left or not right:
            continue
        if (left.claim_id != right.claim_id or left.stance != right.stance
                or set(left.criterion_keys) != set(right.criterion_keys)
                or set(relation.scope_criterion_keys) != set(left.criterion_keys)):
            raise ValueError("Duplicate relation must preserve claim, stance and complete scope")
        one, two = sorted((root(left.origin_key), root(right.origin_key)))
        parents[two] = one
    return {identifier: root(atom.origin_key) for identifier, atom in atoms.items()}


def evaluate_requirements(
    state: DealState,
    claim_id: str,
    requirements: Iterable[Requirement],
) -> RequirementResult:
    """Count each scoped requirement once and preserve qualified refutations."""
    policies = tuple(requirements)
    keys = {item.key for item in policies}
    if not policies or len(keys) != len(policies):
        raise ValueError("Requirements must be nonempty with unique keys")
    claim = next((claim for claim in state.claims if claim.id == claim_id), None)
    if claim is None or not keys <= set(claim.required_criterion_keys):
        raise ValueError("Requirements must reference the same known claim scope")
    credited: set[str] = set()
    conflicts: set[str] = set()
    supporting: set[str] = set()
    refuting: set[str] = set()
    atoms = active_evidence(state)
    for policy in policies:
        for atom in atoms:
            if atom.claim_id != claim_id or policy.key not in atom.criterion_keys:
                continue
            if atom.source_reliability is None or atom.source_reliability < policy.min_reliability:
                continue
            if atom.stance == "refutes":
                # Refutation detection does not assert independent verification.
                conflicts.add(policy.key)
                refuting.add(atom.id)
            elif atom.stance == "supports" and (
                not policy.require_independent
                or (atom.verification_level == "independent_check" and atom.independent_check_reference)
            ):
                credited.add(policy.key)
                supporting.add(atom.id)
    return RequirementResult(frozenset(credited), frozenset(conflicts),
                             tuple(sorted(supporting)), tuple(sorted(refuting)), len(policies))


def ranking_input_digest(state: DealState | Mapping[str, Any]) -> str:
    """Canonical hash of records admitted to the approved evaluation.

    Draft/rejected atoms, questions and relations do not invalidate the current
    approved ranking. Superseded approved atoms are retained as input: their
    lifecycle and approved replacement are what exclude them from credit.
    Ordered lists inside an entity are intentionally never resorted.
    """
    parsed = _state(state)
    claims = [item for item in parsed.claims if item.review_status == "approved"]
    claim_ids = {item.id for item in claims}
    questions = [item for item in parsed.dd_questions
                 if item.review_status == "approved" and item.claim_id in claim_ids]
    atoms = [item for item in parsed.evidence
             if item.review_status == "approved" and item.claim_id in claim_ids]
    atom_ids = {item.id for item in atoms}
    relations = [item for item in parsed.evidence_relations if item.review_status == "approved"
                 and item.from_evidence_id in atom_ids and item.to_evidence_id in atom_ids]
    span_ids = {identifier for item in claims for identifier in item.source_span_ids}
    span_ids.update(identifier for item in atoms for identifier in item.source_span_ids)
    span_ids.update(identifier for item in questions for identifier in item.materiality.source_span_ids)
    spans = [item for item in parsed.source_spans if item.id in span_ids]
    document_ids = {item.document_id for item in spans}
    records = parsed.model_dump(mode="json")
    selected = {
        "documents": [item for item in parsed.documents if item.id in document_ids],
        "source_spans": spans,
        "theses": [item for item in parsed.theses if item.review_status == "approved"],
        "claims": claims, "evidence": atoms, "evidence_relations": relations,
        "dd_questions": questions,
    }
    for name, collection in selected.items():
        records[name] = [item.model_dump(mode="json") for item in collection]
    return input_digest(records)


@dataclass(frozen=True)
class _Priority:
    question_id: str
    canonical_key: str
    gap: Decimal
    materiality: int
    obtainability: int
    score: Decimal
    provisional: bool
    reasons: tuple[str, ...]

    def ordering(self) -> tuple:
        return (-self.score, -self.materiality, -self.gap, -self.obtainability,
                self.canonical_key, self.question_id)


def rank_state(
    state: DealState | Mapping[str, Any],
    *,
    mode: ValidationMode = "contract",
    source_resolver: SourceResolver | None = None,
) -> list[ScoreRow]:
    """Rank validated current records using raw Decimal values, then serialize.

    This computes expected derived workflow state rather than trusting a stored
    resolved flag. The application service separately rejects stale stored
    statuses before committing an update.
    """
    parsed = _state(state)
    # Grounding also checks objective-ratio bins with Decimal arithmetic.
    with localcontext(Context(prec=_PRECISION)):
        validate_grounding(parsed, mode=mode, source_resolver=source_resolver).raise_for_errors()
    approved_claims = {item.id for item in parsed.claims if item.review_status == "approved"}
    priorities: list[_Priority] = []
    for question in parsed.dd_questions:
        if (question.review_status != "approved" or question.claim_id not in approved_claims
                or question.workflow_status in {"rejected", "duplicate"}):
            continue
        result = evaluate_requirements(parsed, question.claim_id, question.requirements)
        if result.resolved:
            continue
        materiality = 3 if question.materiality.score is None else question.materiality.score
        obtainability = 2 if question.obtainability.score is None else question.obtainability.score
        reasons = ["UNRESOLVED_CONFLICT" if result.conflict_keys else "EVIDENCE_GAP"]
        if question.materiality.score is None:
            reasons.append("MATERIALITY_DEFAULT")
        if question.obtainability.score is None:
            reasons.append("OBTAINABILITY_DEFAULT")
        with localcontext(Context(prec=_PRECISION)):
            gap = result.gap
            # Algebraically 9G + 8M + 3O, with a single final division.
            # Multiplying an already rounded repeating gap would spuriously
            # separate mathematically exact ties (e.g. n=9 versus n=15).
            missing = result.total if result.conflict_keys else result.total - len(result.credited_keys)
            numerator = 45 * missing + (8 * materiality + 3 * obtainability) * result.total
            score = Decimal(numerator) / result.total
        priorities.append(_Priority(question.id, question.canonical_key, gap, materiality,
                                    obtainability, score, len(reasons) > 1, tuple(reasons)))
    with localcontext(Context(prec=_PRECISION)):
        priorities.sort(key=lambda item: item.ordering())
    return [ScoreRow(question_id=item.question_id, rank=rank, gap=float(item.gap),
                     materiality=item.materiality, obtainability=item.obtainability,
                     score=float(item.score), provisional=item.provisional,
                     reason_codes=list(item.reasons))
            for rank, item in enumerate(priorities, 1)]


def build_snapshot(
    state: DealState | Mapping[str, Any],
    snapshot_id: str,
    created_at: str,
    trigger_event_id: str | None = None,
    *,
    mode: ValidationMode = "contract",
    source_resolver: SourceResolver | None = None,
) -> RankingSnapshot:
    """Create a new immutable-contract value without changing prior snapshots."""
    parsed = _state(state)
    rows = rank_state(parsed, mode=mode, source_resolver=source_resolver)
    return RankingSnapshot(
        id=snapshot_id, entity_version=1, deal_id=parsed.deal.id,
        state_revision=parsed.state_revision, scoring_version=SCORING_VERSION,
        input_digest=ranking_input_digest(parsed), created_at=created_at,
        trigger_event_id=trigger_event_id, rows=rows,
        top3=[item.question_id for item in rows[:3]],
    )


def display_decimal(value: Decimal | int | float) -> str:
    """Display only: two decimals, half up; never use this value for ordering."""
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Display score must be finite")
    with localcontext(Context(prec=max(_PRECISION, len(number.as_tuple().digits) + 3))):
        return format(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
