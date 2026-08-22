from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol

from insight_desk.core import (
    CandidateEvent,
    EvidenceSpan,
    EventFact,
    IdentityDecision,
    IdentityKey,
    SelectionDecision,
    SelectionSignals,
    TemporalState,
    decide_selection,
    finalize_identity,
    precheck_identity,
)


class TemporalResolutionSource(StrEnum):
    EXTRACTED = "extracted"
    AUXILIARY = "auxiliary"
    UNRESOLVED = "unresolved"


class TemporalAuxiliaryPort(Protocol):
    """Optional Phase 6 temporal/lifecycle helper.

    The frozen production implementation is Groq GPT-OSS 120B. The auxiliary may fill a missing
    lifecycle state from already-bound evidence, but it is not an ownership, identity, selection,
    fact-verification, or publication authority.
    """

    def classify_temporal(self, text: str) -> TemporalState: ...


@dataclass(frozen=True, slots=True)
class TemporalResolution:
    fact_id: str
    state: TemporalState | None
    source: TemporalResolutionSource
    auxiliary_used: bool
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.fact_id.strip():
            raise ValueError("fact_id must be non-empty")
        if self.source is TemporalResolutionSource.UNRESOLVED and self.state is not None:
            raise ValueError("unresolved temporal state must be None")
        if self.source is not TemporalResolutionSource.UNRESOLVED and self.state is None:
            raise ValueError("resolved temporal state must be present")
        if self.error_code is not None and not self.error_code.strip():
            raise ValueError("error_code must be non-empty when present")


@dataclass(frozen=True, slots=True)
class Phase6EventAssessment:
    event: CandidateEvent
    identity_keys: tuple[IdentityKey, ...]
    temporal: tuple[TemporalResolution, ...]
    selection: SelectionDecision

    def __post_init__(self) -> None:
        if len(self.identity_keys) != len(self.event.fact_ids):
            raise ValueError("identity key count must match event fact count")
        if len(self.temporal) != len(self.event.fact_ids):
            raise ValueError("temporal resolution count must match event fact count")
        if tuple(item.fact_id for item in self.temporal) != self.event.fact_ids:
            raise ValueError("temporal resolutions must preserve event fact order")


def _canonical(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized or None


def identity_key_from_fact(fact: EventFact) -> IdentityKey:
    """Build deterministic identity inputs without inventing synonyms or semantic equivalence."""

    return IdentityKey(
        subject_key=_canonical(fact.subject),
        action_key=_canonical(fact.action),
        object_key=_canonical(fact.object),
        event_date_key=_canonical(fact.event_date),
        location_key=_canonical(fact.location),
        cause_key=_canonical(fact.cause),
    )


def _facts_for_event(
    event: CandidateEvent,
    facts: Mapping[str, EventFact],
) -> tuple[EventFact, ...]:
    resolved: list[EventFact] = []
    for fact_id in event.fact_ids:
        try:
            fact = facts[fact_id]
        except KeyError as exc:
            raise ValueError(f"event references missing fact: {fact_id}") from exc
        if fact.fact_id != fact_id:
            raise ValueError(f"fact index key mismatch: {fact_id}")
        resolved.append(fact)
    return tuple(resolved)


def cited_evidence_text(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> str:
    """Return only exact evidence cited by one fact, in citation order."""

    parts: list[str] = []
    for evidence_id in fact.evidence_ids:
        try:
            span = evidence[evidence_id]
        except KeyError as exc:
            raise ValueError(f"fact references missing evidence: {evidence_id}") from exc
        if span.evidence_id != evidence_id:
            raise ValueError(f"evidence index key mismatch: {evidence_id}")
        if span.article_id not in event.article_ids:
            raise ValueError(
                f"fact evidence article is outside candidate event provenance: {evidence_id}"
            )
        parts.append(span.text)
    return "\n\n".join(parts)


def resolve_temporal_state(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
    *,
    auxiliary: TemporalAuxiliaryPort | None = None,
) -> TemporalResolution:
    """Resolve a Phase 6 lifecycle signal without turning the auxiliary into a verifier.

    An explicitly extracted state is preserved as an extracted semantic signal. The optional frozen
    120B auxiliary is called only when the extractor left the lifecycle state missing. Auxiliary
    failure remains item-local and yields an unresolved signal; it never aborts the briefing.
    """

    if fact.fact_id not in event.fact_ids:
        raise ValueError("fact does not belong to candidate event")
    evidence_text = cited_evidence_text(event, fact, evidence)
    if fact.temporal_state is not None:
        return TemporalResolution(
            fact_id=fact.fact_id,
            state=fact.temporal_state,
            source=TemporalResolutionSource.EXTRACTED,
            auxiliary_used=False,
        )
    if auxiliary is None:
        return TemporalResolution(
            fact_id=fact.fact_id,
            state=None,
            source=TemporalResolutionSource.UNRESOLVED,
            auxiliary_used=False,
            error_code="temporal_signal_missing",
        )

    try:
        state = auxiliary.classify_temporal(evidence_text)
    except Exception as exc:  # provider/runtime failure is contained to this event fact
        return TemporalResolution(
            fact_id=fact.fact_id,
            state=None,
            source=TemporalResolutionSource.UNRESOLVED,
            auxiliary_used=True,
            error_code=f"temporal_auxiliary_error:{type(exc).__name__}",
        )
    if not isinstance(state, TemporalState):
        return TemporalResolution(
            fact_id=fact.fact_id,
            state=None,
            source=TemporalResolutionSource.UNRESOLVED,
            auxiliary_used=True,
            error_code="temporal_auxiliary_contract_violation",
        )
    return TemporalResolution(
        fact_id=fact.fact_id,
        state=state,
        source=TemporalResolutionSource.AUXILIARY,
        auxiliary_used=True,
    )


def compare_candidate_identity(
    left: CandidateEvent,
    right: CandidateEvent,
    facts: Mapping[str, EventFact],
    *,
    semantic_same_event: bool | None = None,
) -> IdentityDecision:
    """Apply the frozen identity order to two pre-merge one-fact candidates.

    Phase 6A intentionally emits one candidate per FactDraft. This comparison therefore refuses
    already-merged multi-fact events so that explicit deterministic contradictions are checked before
    any later semantic same-event opinion. With no configured semantic judgment, ambiguity safely
    keeps the candidates separate.
    """

    if left.topic_id != right.topic_id:
        return IdentityDecision(
            same_event=False,
            deterministic_block=True,
            llm_judgment_used=False,
            reason="topic_identity_conflict",
        )
    if len(left.fact_ids) != 1 or len(right.fact_ids) != 1:
        raise ValueError("candidate identity comparison requires pre-merge one-fact events")

    left_fact = _facts_for_event(left, facts)[0]
    right_fact = _facts_for_event(right, facts)[0]
    precheck = precheck_identity(
        identity_key_from_fact(left_fact),
        identity_key_from_fact(right_fact),
    )
    return finalize_identity(precheck, llm_same_event=semantic_same_event)


class Phase6EventEngine:
    """Model-independent Phase 6 wiring after FactDraft -> EventFact/CandidateEvent extraction."""

    def assess(
        self,
        event: CandidateEvent,
        *,
        facts: Mapping[str, EventFact],
        evidence: Mapping[str, EvidenceSpan],
        selection_signals: SelectionSignals,
        temporal_auxiliary: TemporalAuxiliaryPort | None = None,
    ) -> Phase6EventAssessment:
        event_facts = _facts_for_event(event, facts)
        identity_keys = tuple(identity_key_from_fact(fact) for fact in event_facts)
        temporal = tuple(
            resolve_temporal_state(
                event,
                fact,
                evidence,
                auxiliary=temporal_auxiliary,
            )
            for fact in event_facts
        )
        selection = decide_selection(selection_signals)
        return Phase6EventAssessment(
            event=event,
            identity_keys=identity_keys,
            temporal=temporal,
            selection=selection,
        )
