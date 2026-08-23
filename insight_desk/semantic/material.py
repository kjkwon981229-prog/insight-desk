from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact

from .tooling import KiwiMorphologyHelper


_EXPLICIT_NOMINAL_MATERIAL_ACTIONS = frozenset({"선발투수 예고"})
_PUBLISHER_NOTICE_PERMISSION_CUES = ("무단", "사전허가없이", "사전 허가 없이")
_PUBLISHER_NOTICE_RESTRICTION_TERMS = ("복사", "배포", "전재", "재배포", "판매")
_PUBLISHER_NOTICE_LEGAL_CUES = ("책임", "금지", "저작권")


class MaterialEventVerdict(StrEnum):
    MATERIAL = "material"
    DEFER = "defer"


class MaterialEventReason(StrEnum):
    EVIDENCE_BOUND_EXPLICIT_PREDICATE = "evidence_bound_explicit_predicate"
    EVIDENCE_BOUND_EXPLICIT_NOMINAL_EVENT = "evidence_bound_explicit_nominal_event"
    FACT_MISSING = "fact_missing"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_OUTSIDE_EVENT = "evidence_outside_event"
    FACT_FIELD_NOT_LITERAL = "fact_field_not_literal"
    PUBLISHER_NOTICE_BOILERPLATE = "publisher_notice_boilerplate"
    PREDICATE_SIGNAL_MISSING = "predicate_signal_missing"
    LOCAL_HELPER_UNAVAILABLE = "local_helper_unavailable"


@dataclass(frozen=True, slots=True)
class MaterialEventAssessment:
    event_id: str
    verdict: MaterialEventVerdict
    reasons: tuple[MaterialEventReason, ...]

    @property
    def selection_signal(self) -> bool | None:
        return True if self.verdict is MaterialEventVerdict.MATERIAL else None


@lru_cache(maxsize=1)
def _shared_morphology() -> KiwiMorphologyHelper:
    return KiwiMorphologyHelper()


def _cited_text(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> tuple[str | None, MaterialEventReason | None]:
    parts: list[str] = []
    allowed_articles = set(event.article_ids)
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None:
            return None, MaterialEventReason.EVIDENCE_MISSING
        if span.article_id not in allowed_articles:
            return None, MaterialEventReason.EVIDENCE_OUTSIDE_EVENT
        parts.append(span.text)
    return "\n\n".join(parts), None


def _publisher_notice_boilerplate(text: str) -> bool:
    """Reject only high-confidence publisher reuse/legal notices, not reported copyright events."""

    return (
        any(cue in text for cue in _PUBLISHER_NOTICE_PERMISSION_CUES)
        and sum(term in text for term in _PUBLISHER_NOTICE_RESTRICTION_TERMS) >= 2
        and any(cue in text for cue in _PUBLISHER_NOTICE_LEGAL_CUES)
    )


def assess_material_event(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: KiwiMorphologyHelper | None = None,
) -> MaterialEventAssessment:
    """Return MATERIAL only for event-local, literal, explicit evidence; otherwise DEFER."""

    if morphology is None:
        try:
            morphology = _shared_morphology()
        except RuntimeError:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.LOCAL_HELPER_UNAVAILABLE,),
            )

    used_nominal = False
    for fact_id in event.fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            return MaterialEventAssessment(
                event.event_id, MaterialEventVerdict.DEFER, (MaterialEventReason.FACT_MISSING,)
            )
        text, evidence_error = _cited_text(event, fact, evidence)
        if evidence_error is not None or text is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (evidence_error or MaterialEventReason.EVIDENCE_MISSING,),
            )
        if _publisher_notice_boilerplate(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.PUBLISHER_NOTICE_BOILERPLATE,),
            )
        literal_fields = (fact.subject, fact.action) + ((fact.object,) if fact.object is not None else ())
        if any(value not in text for value in literal_fields):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_FIELD_NOT_LITERAL,),
            )
        if any(token.tag in {"VV", "XSV"} for token in morphology.analyze(fact.action)):
            continue
        if fact.action in _EXPLICIT_NOMINAL_MATERIAL_ACTIONS:
            used_nominal = True
            continue
        return MaterialEventAssessment(
            event.event_id,
            MaterialEventVerdict.DEFER,
            (MaterialEventReason.PREDICATE_SIGNAL_MISSING,),
        )

    reason = (
        MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_NOMINAL_EVENT
        if used_nominal
        else MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE
    )
    return MaterialEventAssessment(event.event_id, MaterialEventVerdict.MATERIAL, (reason,))
