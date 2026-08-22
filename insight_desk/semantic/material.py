from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact

from .tooling import KiwiMorphologyHelper


class MaterialEventVerdict(StrEnum):
    MATERIAL = "material"
    DEFER = "defer"


class MaterialEventReason(StrEnum):
    EVIDENCE_BOUND_EXPLICIT_PREDICATE = "evidence_bound_explicit_predicate"
    FACT_MISSING = "fact_missing"
    EVIDENCE_MISSING = "evidence_missing"
    FACT_FIELD_NOT_LITERAL = "fact_field_not_literal"
    PREDICATE_SIGNAL_MISSING = "predicate_signal_missing"
    LOCAL_HELPER_UNAVAILABLE = "local_helper_unavailable"


@dataclass(frozen=True, slots=True)
class MaterialEventAssessment:
    event_id: str
    verdict: MaterialEventVerdict
    reasons: tuple[MaterialEventReason, ...]

    @property
    def selection_signal(self) -> bool | None:
        if self.verdict is MaterialEventVerdict.MATERIAL:
            return True
        return None


def _cited_text(fact: EventFact, evidence: Mapping[str, EvidenceSpan]) -> str | None:
    parts: list[str] = []
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None:
            return None
        parts.append(span.text)
    return "\n\n".join(parts)


def assess_material_event(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: KiwiMorphologyHelper | None = None,
) -> MaterialEventAssessment:
    """Produce a precision-first material-event signal from already-structured facts.

    `MATERIAL` requires literal evidence binding plus an explicit verbal predicate in every fact's
    action clause. Missing/normalized/ambiguous structure returns `DEFER`, never an invented negative
    label. This function is independent from briefing selection and never uses old selection TNs as
    material-event truth.
    """

    if morphology is None:
        try:
            morphology = KiwiMorphologyHelper()
        except RuntimeError:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.LOCAL_HELPER_UNAVAILABLE,),
            )

    for fact_id in event.fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_MISSING,),
            )
        text = _cited_text(fact, evidence)
        if text is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.EVIDENCE_MISSING,),
            )
        literal_fields = (fact.subject, fact.action)
        if fact.object is not None:
            literal_fields += (fact.object,)
        if any(value not in text for value in literal_fields):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_FIELD_NOT_LITERAL,),
            )
        action_tokens = morphology.analyze(fact.action)
        if not any(token.tag in {"VV", "XSV"} for token in action_tokens):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.PREDICATE_SIGNAL_MISSING,),
            )

    return MaterialEventAssessment(
        event.event_id,
        MaterialEventVerdict.MATERIAL,
        (MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE,),
    )
