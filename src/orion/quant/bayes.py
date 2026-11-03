"""Binary Bayesian arithmetic and conservative evidence-dependence control.

Probability parameters are analyst-authored synthetic assumptions, never
automatically inferred from a company's claims. The ledger is a calculation
component; its ``approved`` input must come from the existing review boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
import math
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator

from orion.domain.models import StrictContract


def probability(value: int | float, name: str = "probability") -> float:
    """Validate without silently accepting booleans, NaN, infinities or text."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite numeric probability")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite numeric probability") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")
    return number


def posterior(prior: float, likelihood_h: float, likelihood_not_h: float) -> float:
    """P(H|E); raise for an event with zero prior-predictive probability.

    Degenerate priors (0 or 1) are allowed, but impossible observations do not
    become a fabricated posterior. Scaling prevents avoidable underflow for
    very small, nonzero likelihoods.
    """
    p = probability(prior, "prior")
    a = probability(likelihood_h, "likelihood_h")
    b = probability(likelihood_not_h, "likelihood_not_h")
    scale = max(a, b)
    if scale == 0.0:
        raise ValueError("Evidence has zero prior-predictive probability")
    numerator = (a / scale) * p
    alternative = (b / scale) * (1.0 - p)
    denominator = numerator + alternative
    if denominator == 0.0:
        raise ValueError("Evidence has zero prior-predictive probability")
    return numerator / denominator


def binary_posteriors(prior: float, sensitivity: float, false_positive: float) -> dict[str, float | None]:
    """Positive/negative posterior and predictive masses of an exhaustive test.

    Impossible outcomes receive ``None`` rather than an arbitrary posterior.
    The negative likelihoods are complements, not swapped positive likelihoods.
    """
    p = probability(prior, "prior")
    a = probability(sensitivity, "sensitivity")
    b = probability(false_positive, "false_positive")
    positive_mass = p * a + (1.0 - p) * b
    negative_mass = p * (1.0 - a) + (1.0 - p) * (1.0 - b)
    return {
        "positive": posterior(p, a, b) if positive_mass else None,
        "negative": posterior(p, 1.0 - a, 1.0 - b) if negative_mass else None,
        "p_positive": positive_mass,
        "p_negative": negative_mass,
    }


class ProbabilityAssumptions(StrictContract):
    """Versioned provenance for one hypothetical observation likelihood."""

    assumption_id: Annotated[str, Field(min_length=1)]
    assumption_source: Annotated[str, Field(min_length=1)]
    author_id: Annotated[str, Field(min_length=1)]
    as_of: Annotated[str, Field(min_length=1)]
    version: Annotated[int, Field(ge=1)] = 1
    interpretation: Literal["synthetic_scenario_not_empirical"] = "synthetic_scenario_not_empirical"
    prior: float | None
    likelihood_h: float | None
    likelihood_not_h: float | None

    @field_validator("prior", "likelihood_h", "likelihood_not_h", mode="before")
    @classmethod
    def check_probability(cls, value):
        return None if value is None else probability(value)

    @field_validator("assumption_id", "assumption_source", "author_id", "as_of")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Assumption metadata must not be whitespace")
        return value

    @field_validator("as_of")
    @classmethod
    def valid_date(cls, value):
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("as_of must use YYYY-MM-DD")
        date.fromisoformat(value)
        return value

    @property
    def complete(self) -> bool:
        return all(v is not None for v in (self.prior, self.likelihood_h, self.likelihood_not_h))


class ConditionalLikelihoodModel(StrictContract):
    """Reviewed chain-rule scenario, bound to the complete accepted history.

    It asserts that the accompanying likelihoods mean P(new E | H, history)
    and P(new E | not H, history). This is an authored conditional joint model,
    not evidence that the records are independent or empirically calibrated.
    """

    model_id: Annotated[str, Field(min_length=1)]
    hypothesis_id: Annotated[str, Field(min_length=1)]
    evidence_id: Annotated[str, Field(min_length=1)]
    assumption_id: Annotated[str, Field(min_length=1)]
    assumption_version: Annotated[int, Field(ge=1)] = 1
    likelihood_h: float
    likelihood_not_h: float
    conditioning_evidence_ids: Annotated[list[str], Field(min_length=1)]
    conditioning_group_ids: Annotated[list[str], Field(min_length=1)]
    assumption_source: Annotated[str, Field(min_length=1)]
    reviewer_id: Annotated[str, Field(min_length=1)]
    reviewed_at: Annotated[str, Field(min_length=1)]
    review_status: Literal["approved"]
    semantics: Literal["given_complete_accepted_history"] = "given_complete_accepted_history"

    @field_validator("likelihood_h", "likelihood_not_h", mode="before")
    @classmethod
    def valid_probability(cls, value):
        return probability(value)

    @field_validator("model_id", "hypothesis_id", "evidence_id", "assumption_id",
                     "assumption_source", "reviewer_id", "reviewed_at")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Conditional model metadata must not be whitespace")
        return value

    @field_validator("conditioning_evidence_ids", "conditioning_group_ids")
    @classmethod
    def unique_nonempty(cls, values):
        if len(set(values)) != len(values) or any(not value.strip() for value in values):
            raise ValueError("Conditioning IDs must be unique and nonempty")
        return values

    @field_validator("reviewed_at")
    @classmethod
    def valid_date(cls, value):
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("reviewed_at must use YYYY-MM-DD")
        date.fromisoformat(value)
        return value


@dataclass(frozen=True)
class BeliefSnapshot:
    """Audit output; intentionally separate from the v1 ranking contract."""

    hypothesis_id: str
    evidence_id: str
    evidence_group_id: str
    source_fingerprint: str
    status: Literal["applied", "unapproved", "missing_parameters", "duplicate", "dependent"]
    prior: float | None
    posterior: float | None
    assumption_id: str
    assumption_version: int
    assumption_source: str
    reason: str
    conditional_model_id: str | None = None
    conditional_model_source: str | None = None
    conditioning_evidence_ids: tuple[str, ...] = ()
    conditioning_group_ids: tuple[str, ...] = ()
    likelihood_h: float | None = None
    likelihood_not_h: float | None = None
    assumption_author_id: str | None = None
    assumption_as_of: str | None = None
    conditional_reviewer_id: str | None = None
    conditional_reviewed_at: str | None = None


class BayesianLedger:
    """Sequential updates with per-hypothesis group and content deduplication.

    Distinct independence groups are an explicit analyst assumption. A shared
    group or declared dependency blocks a second likelihood multiplication.
    Different hypotheses may legitimately use the same evidence, but must have
    their own priors and likelihood assumptions. There is no joint-probability
    model is supplied by default. Correlated additions require an explicitly
    reviewed conditional model bound to every already-applied observation.
    """

    def __init__(self) -> None:
        self._beliefs: dict[str, float] = {}
        self._groups: dict[str, set[str]] = {}
        self._fingerprints: dict[str, set[str]] = {}
        self._dependencies: dict[str, dict[str, set[str]]] = {}
        self._evidence_payloads: dict[tuple[str, str], str] = {}
        self._accepted_groups: dict[tuple[str, str], str] = {}
        self._source_groups: dict[tuple[str, str], str] = {}
        self._history: list[BeliefSnapshot] = []

    @property
    def beliefs(self) -> dict[str, float]:
        return dict(self._beliefs)

    @property
    def history(self) -> tuple[BeliefSnapshot, ...]:
        return tuple(self._history)

    def snapshot(self) -> dict:
        return {
            "quant_version": "1.0.0",
            "interpretation": "synthetic_scenario_not_empirical",
            "beliefs": self.beliefs,
            "dependence_graph": {
                hypothesis: {group: sorted(neighbors) for group, neighbors in sorted(graph.items())}
                for hypothesis, graph in sorted(self._dependencies.items())
            },
            "history": [asdict(item) for item in self._history],
        }

    def update(
        self, *, hypothesis_id: str, evidence_id: str, evidence_group_id: str,
        source_fingerprint: str, assumptions: ProbabilityAssumptions,
        approved: bool, dependent_group_ids: tuple[str, ...] = (),
        conditional_model: ConditionalLikelihoodModel | None = None,
    ) -> BeliefSnapshot:
        for label, identifier in (("hypothesis_id", hypothesis_id), ("evidence_id", evidence_id),
                                  ("evidence_group_id", evidence_group_id)):
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"{label} is required")
        if not isinstance(source_fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", source_fingerprint):
            raise ValueError("source_fingerprint must be a lowercase SHA-256 digest of source content")
        if type(approved) is not bool:
            raise ValueError("approved must be an explicit boolean from the review boundary")
        if not isinstance(dependent_group_ids, tuple) or any(
            not isinstance(x, str) or not x.strip() for x in dependent_group_ids
        ):
            raise ValueError("dependent_group_ids must be a tuple of nonempty group IDs")
        parsed = ProbabilityAssumptions.model_validate(assumptions.model_dump(mode="json"))
        conditional = None
        if conditional_model is not None:
            conditional = ConditionalLikelihoodModel.model_validate(conditional_model.model_dump(mode="json"))
            if (conditional.hypothesis_id != hypothesis_id or conditional.evidence_id != evidence_id
                    or conditional.assumption_id != parsed.assumption_id
                    or conditional.assumption_version != parsed.version
                    or conditional.likelihood_h != parsed.likelihood_h
                    or conditional.likelihood_not_h != parsed.likelihood_not_h):
                raise ValueError("Conditional model does not match the hypothesis, observation and probability assumption")
        prior_value = self._beliefs.get(hypothesis_id, parsed.prior)
        payload = sha256(json.dumps({
            "group": evidence_group_id, "fingerprint": source_fingerprint,
            "assumptions": parsed.model_dump(mode="json"),
            "dependencies": sorted(set(dependent_group_ids)),
            "conditional_model": conditional.model_dump(mode="json") if conditional else None,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        identity = (hypothesis_id, evidence_id)
        previous_payload = self._evidence_payloads.get(identity)
        if previous_payload is not None and previous_payload != payload:
            raise ValueError("An applied evidence ID cannot be reused with changed content or assumptions")
        if conditional is not None and previous_payload is None:
            expected_ids = {identifier for (hypothesis, identifier) in self._accepted_groups if hypothesis == hypothesis_id}
            expected_groups = {group for (hypothesis, _), group in self._accepted_groups.items() if hypothesis == hypothesis_id}
            if not expected_ids or set(conditional.conditioning_evidence_ids) != expected_ids or set(
                conditional.conditioning_group_ids
            ) != expected_groups:
                raise ValueError("Conditional model must match the complete accepted evidence/group history exactly")
        groups = self._groups.get(hypothesis_id, set())
        fingerprints = self._fingerprints.get(hypothesis_id, set())
        old_graph = self._dependencies.get(hypothesis_id, {})
        graph = {group: set(neighbors) for group, neighbors in old_graph.items()}
        if approved:
            graph.setdefault(evidence_group_id, set())
            declared = set(dependent_group_ids)
            if conditional:
                declared.update(conditional.conditioning_group_ids)
            for other in declared:
                graph[evidence_group_id].add(other)
                graph.setdefault(other, set()).add(evidence_group_id)
            canonical_source_group = self._source_groups.get((hypothesis_id, source_fingerprint))
            if canonical_source_group is not None:
                graph[evidence_group_id].add(canonical_source_group)
                graph.setdefault(canonical_source_group, set()).add(evidence_group_id)
        connected: set[str] = set()
        pending = [evidence_group_id]
        while pending:
            group = pending.pop()
            if group not in connected:
                connected.add(group)
                pending.extend(graph.get(group, ()))
        prior_components = set()
        for accepted_group in connected & groups:
            seen: set[str] = set()
            todo = [accepted_group]
            while todo:
                group = todo.pop()
                if group not in seen:
                    seen.add(group)
                    todo.extend(old_graph.get(group, ()))
            prior_components.add(min(seen))
        if approved and conditional is None and len(prior_components) > 1:
            raise ValueError("New dependence joins previously counted groups; replay is required before further updating")
        status: str
        reason: str
        result_value = prior_value
        if not approved:
            status, reason = "unapproved", "Analyst approval is required; belief was unchanged."
        elif previous_payload is not None or source_fingerprint in fingerprints:
            status, reason = "duplicate", "An applied evidence ID or source-content fingerprint was already counted."
        elif connected & groups and conditional is None:
            status, reason = "dependent", "Correlated evidence was not multiplied without a joint probability model."
        elif not parsed.complete:
            status, reason = "missing_parameters", "A probability parameter is absent; use qualitative evidence-gap ranking."
        else:
            if hypothesis_id in self._beliefs and not math.isclose(
                parsed.prior, prior_value, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError("Assumption prior is stale; it must equal the current hypothesis posterior")
            result_value = posterior(parsed.prior, parsed.likelihood_h, parsed.likelihood_not_h)
            status = "applied"
            reason = (
                "Applied reviewed P(new evidence | hypothesis, complete accepted history) chain-rule likelihoods; independence is not assumed."
                if conditional else "Approved source from a new analyst-defined independent group."
            )
        item = BeliefSnapshot(
            hypothesis_id=hypothesis_id, evidence_id=evidence_id,
            evidence_group_id=evidence_group_id, source_fingerprint=source_fingerprint,
            status=status, prior=prior_value, posterior=result_value,
            assumption_id=parsed.assumption_id, assumption_version=parsed.version,
            assumption_source=parsed.assumption_source, reason=reason,
            conditional_model_id=conditional.model_id if conditional else None,
            conditional_model_source=conditional.assumption_source if conditional else None,
            conditioning_evidence_ids=tuple(conditional.conditioning_evidence_ids) if conditional else (),
            conditioning_group_ids=tuple(conditional.conditioning_group_ids) if conditional else (),
            likelihood_h=parsed.likelihood_h, likelihood_not_h=parsed.likelihood_not_h,
            assumption_author_id=parsed.author_id, assumption_as_of=parsed.as_of,
            conditional_reviewer_id=conditional.reviewer_id if conditional else None,
            conditional_reviewed_at=conditional.reviewed_at if conditional else None,
        )
        # All checks and arithmetic finish before mutating state.
        if status == "applied":
            self._beliefs[hypothesis_id] = result_value
            self._groups.setdefault(hypothesis_id, set()).add(evidence_group_id)
            self._fingerprints.setdefault(hypothesis_id, set()).add(source_fingerprint)
            self._evidence_payloads[identity] = payload
            self._accepted_groups[identity] = evidence_group_id
            self._source_groups[(hypothesis_id, source_fingerprint)] = evidence_group_id
        if approved:
            self._dependencies[hypothesis_id] = graph
        self._history.append(item)
        return item
