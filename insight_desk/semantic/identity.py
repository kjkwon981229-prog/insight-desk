from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from insight_desk.core import CandidateEvent, EventFact, IdentityDecision

from .events import compare_candidate_identity


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Final pairwise Phase 6 identity outcome.

    A positive optional semantic judgment may merge two non-conflicting candidates. Every other
    outcome, including unresolved ambiguity, is a valid fail-safe resolution that keeps the
    candidates separate. This object never performs retrieval or calls a model.
    """

    decision: IdentityDecision
    events: tuple[CandidateEvent, ...]

    def __post_init__(self) -> None:
        expected = 1 if self.decision.same_event else 2
        if len(self.events) != expected:
            raise ValueError("identity resolution event count does not match decision")


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
