from __future__ import annotations

"""Bounded Event Understanding compatibility owner for the legacy extraction bridge.

This module is deliberately provider-free. It does not create CanonicalEvent objects and it does
not replace the qualified Event Understanding provider contract. It classifies the already
extracted, evidence-bound one-fact CandidateEvent so the production loop can distinguish a primary
news event from contextual/analytical prose and from unresolved context before Phase 6 selection.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    TopicRelation,
    UnderstandingStatus,
)


class MorphologyPort(Protocol):
    def analyze(self, text: str): ...


@dataclass(frozen=True, slots=True)
class CompatibilityEventUnderstandingDecision:
    status: UnderstandingStatus
    article_role: ArticleEventRole
    topic_relation: TopicRelation
    publishable_event: bool
    reasons: tuple[str, ...] = ()


_CONTEXT_SUBJECT_STEMS = (
    "그",
    "그녀",
    "그들",
    "이들",
    "그것",
    "이것",
    "해당",
    "이는",
    "이를",
    "이러한",
    "그러한",
)

# Generic epistemic/evaluative predicates describe interpretation or expected effect rather than a
# newly occurring event. This is intentionally topic-agnostic and only operates on the extracted
# predicate already bound to source evidence.
_ANALYTICAL_PREDICATES = (
    "평가된다",
    "평가했다",
    "전망된다",
    "전망했다",
    "예상된다",
    "예상했다",
    "분석된다",
    "분석했다",
    "기대된다",
    "기대했다",
    "것으로 보인다",
    "것으로 관측된다",
    "가능성이 있다",
    "의미가 있다",
    "효과가 있을",
    "효과가 기대",
)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _is_context_dependent_subject(subject: str) -> bool:
    value = _normalized(subject)
    if not value:
        return True
    return any(value.startswith(stem) for stem in _CONTEXT_SUBJECT_STEMS)


def _is_analytical_predicate(action: str) -> bool:
    value = _normalized(action)
    return any(predicate in value for predicate in _ANALYTICAL_PREDICATES)


def _has_explicit_predicate(action: str, morphology: MorphologyPort | None) -> bool:
    if not _normalized(action):
        return False
    if morphology is None:
        return True
    try:
        tokens = tuple(morphology.analyze(action))
    except Exception:
        return True
    if not tokens:
        return True
    return any(str(getattr(token, "tag", "")).startswith(("V", "XSV", "XSA")) for token in tokens)


def _evidence_is_local(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> bool:
    """Check provenance locality only; Phase 6 owns fact-field evidence integrity.

    Re-validating literal fact fields here would make Event Understanding a second evidence-
    integrity authority and is brittle to ordinary Korean particle/morphology variation. This
    compatibility owner therefore proves only that every cited span exists, belongs to one of the
    event's source articles, and contains non-empty source text.
    """

    if not fact.evidence_ids:
        return False
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None or span.article_id not in event.article_ids or not span.text.strip():
            return False
    return True


def assess_compatibility_event_understanding(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: MorphologyPort | None,
    now: datetime,
) -> CompatibilityEventUnderstandingDecision:
    """Classify one legacy bridge event without inventing new event semantics.

    ``now`` is accepted so the compatibility boundary has the same explicit temporal dependency as
    a future Event Understanding owner. It is not used to reinterpret evidence here.
    """

    del now
    if len(event.fact_ids) != 1:
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("compat_requires_single_fact",),
        )

    fact = facts.get(event.fact_ids[0])
    if fact is None:
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("fact_missing",),
        )

    if not _evidence_is_local(event, fact, evidence):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("evidence_not_local",),
        )

    if _is_context_dependent_subject(fact.subject):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("context_dependent_actor",),
        )

    if not _has_explicit_predicate(fact.action, morphology):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("predicate_unresolved",),
        )

    if _is_analytical_predicate(fact.action):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=("analytical_context",),
        )

    return CompatibilityEventUnderstandingDecision(
        status=UnderstandingStatus.RESOLVED,
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        publishable_event=True,
    )
