from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EventFact, IdentityDecision, VerificationCheck

from .events import compare_candidate_identity


class IdentityClaimVerifier(Protocol):
    verifier_id: str
    model_id: str

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck: ...


@dataclass(frozen=True, slots=True)
class SemanticIdentityJudgment:
    """Availability-aware semantic same-event opinion for one non-conflicting pair."""

    same_event: bool | None
    reason: str
    secondary_checks: int
    primary_checks: int

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("identity judgment reason must be non-empty")
        if self.secondary_checks < 0 or self.primary_checks < 0:
            raise ValueError("identity judgment check counts must be non-negative")


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Final pairwise Phase 6 identity outcome.

    A positive optional semantic judgment may merge two non-conflicting candidates. Every other
    outcome, including unresolved ambiguity, is a valid fail-safe resolution that keeps the
    candidates separate.
    """

    decision: IdentityDecision
    events: tuple[CandidateEvent, ...]

    def __post_init__(self) -> None:
        expected = 1 if self.decision.same_event else 2
        if len(self.events) != expected:
            raise ValueError("identity resolution event count does not match decision")


def _stable_identity_token(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def _safe_identity_verify(
    verifier: IdentityClaimVerifier,
    *,
    direction: str,
    claim_text: str,
    evidence_text: str,
) -> VerificationCheck:
    token = _stable_identity_token(direction, claim_text, evidence_text)
    evidence_ids = (f"identity-evidence:{token}",)
    check_id = f"identity-check:{_stable_identity_token(token, verifier.verifier_id)}"
    try:
        check = verifier.verify(
            check_id=check_id,
            claim_text=claim_text,
            evidence_text=evidence_text,
            evidence_ids=evidence_ids,
        )
    except Exception as exc:
        return VerificationCheck(
            check_id=check_id,
            verifier_id=verifier.verifier_id,
            model_id=verifier.model_id,
            evidence_ids=evidence_ids,
            entailed=None,
            error_code=f"identity_verifier_exception:{type(exc).__name__.lower()[:80] or 'unknown'}",
            zero_cost=True,
        )
    if check.check_id != check_id:
        raise ValueError("identity verifier returned mismatched check_id")
    if check.verifier_id != verifier.verifier_id:
        raise ValueError("identity verifier returned mismatched verifier_id")
    if check.evidence_ids != evidence_ids:
        raise ValueError("identity verifier returned mismatched evidence_ids")
    return check


def judge_same_event_mutual_entailment(
    left_text: str,
    right_text: str,
    *,
    primary: IdentityClaimVerifier,
    secondary: IdentityClaimVerifier,
) -> SemanticIdentityJudgment:
    """Judge event equivalence only after two-way support from two independent verifier slots.

    The local/secondary slot runs first so clearly different or unavailable pairs spend no external
    provider budget. A positive same-event judgment requires left->right and right->left entailment
    from both slots. Explicit negative support means different-event; missing/provider-failed results
    remain unavailable and therefore keep the events separate under the frozen identity policy.
    """

    left = " ".join(left_text.split()).strip()
    right = " ".join(right_text.split()).strip()
    if not left or not right:
        return SemanticIdentityJudgment(None, "identity_text_missing", 0, 0)
    if primary.verifier_id == secondary.verifier_id:
        raise ValueError("identity primary and secondary verifier ids must be independent")

    directions = (("left_to_right", left, right), ("right_to_left", right, left))
    secondary_checks = 0
    for direction, claim, evidence in directions:
        check = _safe_identity_verify(
            secondary,
            direction=direction,
            claim_text=claim,
            evidence_text=evidence,
        )
        secondary_checks += 1
        if check.entailed is False:
            return SemanticIdentityJudgment(
                False,
                "secondary_rejected_equivalence",
                secondary_checks,
                0,
            )
        if check.entailed is None:
            return SemanticIdentityJudgment(
                None,
                "secondary_identity_unavailable",
                secondary_checks,
                0,
            )

    primary_checks = 0
    for direction, claim, evidence in directions:
        check = _safe_identity_verify(
            primary,
            direction=direction,
            claim_text=claim,
            evidence_text=evidence,
        )
        primary_checks += 1
        if check.entailed is False:
            return SemanticIdentityJudgment(
                False,
                "primary_rejected_equivalence",
                secondary_checks,
                primary_checks,
            )
        if check.entailed is None:
            return SemanticIdentityJudgment(
                None,
                "primary_identity_unavailable",
                secondary_checks,
                primary_checks,
            )

    return SemanticIdentityJudgment(
        True,
        "mutual_entailment_supported_by_both_slots",
        secondary_checks,
        primary_checks,
    )


def _merged_event_id(left: CandidateEvent, right: CandidateEvent) -> str:
    parts = [
        left.topic_id,
        *sorted((left.event_id, right.event_id)),
        *sorted(set(left.fact_ids + right.fact_ids)),
        *sorted(set(left.article_ids + right.article_ids)),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"identity-{digest}"


def merge_candidate_events(
    left: CandidateEvent,
    right: CandidateEvent,
    decision: IdentityDecision,
) -> CandidateEvent:
    """Merge provenance only after identity has explicitly resolved to same-event."""

    if not decision.same_event:
        raise ValueError("candidate merge requires an explicit same-event decision")
    if decision.deterministic_block:
        raise ValueError("deterministic identity block can never be merged")
    if left.topic_id != right.topic_id:
        raise ValueError("candidate merge cannot cross topics")

    return CandidateEvent(
        event_id=_merged_event_id(left, right),
        topic_id=left.topic_id,
        fact_ids=tuple(sorted(set(left.fact_ids + right.fact_ids))),
        article_ids=tuple(sorted(set(left.article_ids + right.article_ids))),
    )


def resolve_candidate_pair(
    left: CandidateEvent,
    right: CandidateEvent,
    facts: Mapping[str, EventFact],
    *,
    semantic_same_event: bool | None = None,
) -> IdentityResolution:
    """Complete the frozen identity policy for one pre-merge candidate pair.

    Deterministic contradictions are checked first by `compare_candidate_identity`. Optional semantic
    judgment can only operate after those checks. If no semantic judgment is configured or ambiguity
    remains, the production-safe result is two separate events rather than a blocked pipeline.
    """

    decision = compare_candidate_identity(
        left,
        right,
        facts,
        semantic_same_event=semantic_same_event,
    )
    if not decision.same_event:
        return IdentityResolution(decision=decision, events=(left, right))
    return IdentityResolution(
        decision=decision,
        events=(merge_candidate_events(left, right, decision),),
    )
