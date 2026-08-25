from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from functools import lru_cache
from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact
from insight_desk.story_admission import (
    StoryAdmissionInput,
    StoryAdmissionStage,
    evaluate_story_admission,
)

from .tooling import KiwiMorphologyHelper


_EXPLICIT_NOMINAL_MATERIAL_ACTIONS = frozenset({"선발투수 예고"})


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
    DEPICTIVE_SPORTS_CAPTION = "depictive_sports_caption"
    CONTEXT_DEPENDENT_FRAGMENT = "context_dependent_fragment"
    NON_EVENT_ANALYTICAL_JUDGMENT = "non_event_analytical_judgment"
    CONDITIONAL_ANALYTICAL_SCENARIO = "conditional_analytical_scenario"
    STALE_DATED_CONTEXT = "stale_dated_context"
    STALE_EXPLICIT_PAST_EVENT = "stale_explicit_past_event"
    STALE_SPORTS_RETROSPECTIVE = "stale_sports_retrospective"
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


def _material_admission_text(text: str, fact: EventFact) -> str:
    """Project a provenance-bound EventFact date into the shared freshness decision.

    The evidence bytes stay untouched for literal-field and verification checks. A date recovered
    from adjacent exact source context is metadata on the same EventFact; formatting it as an
    explicit Korean date lets the existing StoryAdmissionDecision apply its canonical freshness
    rule instead of creating a second temporal policy here.
    """

    if fact.event_date is None:
        return text
    try:
        parsed = date.fromisoformat(fact.event_date)
    except ValueError:
        return text
    return f"{parsed.year}년 {parsed.month}월 {parsed.day}일 {text}"


def _shared_material_rejection(codes: tuple[str, ...]) -> MaterialEventReason | None:
    code_set = set(codes)
    ordered = (
        ("MATERIAL_PUBLISHER_NOTICE_BOILERPLATE", MaterialEventReason.PUBLISHER_NOTICE_BOILERPLATE),
        ("MATERIAL_DEPICTIVE_SPORTS_CAPTION", MaterialEventReason.DEPICTIVE_SPORTS_CAPTION),
        ("MATERIAL_CONTEXT_DEPENDENT_FRAGMENT", MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT),
        ("MATERIAL_NON_EVENT_ANALYTICAL_JUDGMENT", MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT),
        ("MATERIAL_CONDITIONAL_ANALYTICAL_SCENARIO", MaterialEventReason.CONDITIONAL_ANALYTICAL_SCENARIO),
        ("MATERIAL_STALE_SPORTS_RETROSPECTIVE", MaterialEventReason.STALE_SPORTS_RETROSPECTIVE),
        ("MATERIAL_STALE_EXPLICIT_PAST_EVENT", MaterialEventReason.STALE_EXPLICIT_PAST_EVENT),
        ("MATERIAL_STALE_DATED_CONTEXT", MaterialEventReason.STALE_DATED_CONTEXT),
    )
    for code, reason in ordered:
        if code in code_set:
            return reason
    return None


def assess_material_event(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: KiwiMorphologyHelper | None = None,
    now: datetime | None = None,
) -> MaterialEventAssessment:
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
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_MISSING,),
            )
        text, evidence_error = _cited_text(event, fact, evidence)
        if evidence_error is not None or text is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (evidence_error or MaterialEventReason.EVIDENCE_MISSING,),
            )

        admission_text = _material_admission_text(text, fact)
        admission = evaluate_story_admission(
            StoryAdmissionInput(
                stage=StoryAdmissionStage.MATERIAL,
                topic=event.topic_id,
                summary=admission_text,
                source_text=admission_text,
                subject=fact.subject,
                now=now or datetime.now(timezone.utc),
            )
        )
        if not admission.accepted:
            reason = _shared_material_rejection(admission.compatibility_codes)
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (reason or MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
            )

        literal_fields = (fact.subject, fact.action) + (
            (fact.object,) if fact.object is not None else ()
        )
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
    return MaterialEventAssessment(
        event.event_id,
        MaterialEventVerdict.MATERIAL,
        (reason,),
    )
