from __future__ import annotations

"""Bounded Event Understanding compatibility owner for the legacy extraction bridge.

This module is deliberately provider-free. It does not create CanonicalEvent objects and it does
not replace the qualified Event Understanding provider contract. It classifies the already
extracted, evidence-bound CandidateEvents jointly at article scope so the production loop can
separate one source-central news event from contextual/analytical facts before Phase 6 selection.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, RawArticle
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.event_predicate_v2 import PredicateCompleteness, assess_event_predicate


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


def _morphology_tokens(text: str, morphology: MorphologyPort | None) -> tuple[object, ...] | None:
    if morphology is None:
        return None
    try:
        return tuple(morphology.analyze(text))
    except Exception:
        return None


def _has_explicit_predicate(action: str, morphology: MorphologyPort | None) -> bool:
    if not _normalized(action):
        return False
    if morphology is None:
        # Compatibility direct-call behavior. Production article understanding supplies morphology;
        # the shared owner is authoritative whenever structural analysis is available.
        return True
    assessment = assess_event_predicate(action, morphology=morphology)
    return assessment.completeness is PredicateCompleteness.COMPLETE


def _is_copular_definition(action: str, morphology: MorphologyPort | None) -> bool:
    """Identify a static classification/definition by its final morphological predicate only."""

    tokens = _morphology_tokens(action, morphology)
    if not tokens:
        return False
    predicate_tags = [
        str(getattr(token, "tag", ""))
        for token in tokens
        if str(getattr(token, "tag", "")).startswith(("V", "XSV", "XSA"))
    ]
    return bool(predicate_tags) and predicate_tags[-1] in {"VCP", "VCN"}


def _actor_specificity(subject: str, morphology: MorphologyPort | None) -> int:
    """Return 1 only when morphology exposes a proper/name-like actor surface.

    Article centrality must not treat a numeric count or generic common noun as stronger merely
    because it appears in the lead. NNP and foreign-name (SL) tokens are source-derived structural
    evidence of a specific actor; no entity dictionary or topic vocabulary is used.
    """

    tokens = _morphology_tokens(subject, morphology)
    if not tokens:
        return 0
    return int(any(str(getattr(token, "tag", "")) in {"NNP", "SL"} for token in tokens))


def _evidence_is_local(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> bool:
    """Check provenance locality only; Phase 6 owns fact-field evidence integrity."""

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
    """Classify one legacy bridge event without inventing new event semantics."""

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

    if _is_copular_definition(fact.action, morphology):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=("copular_definition_context",),
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


def _first_sentence_end(body: str) -> int:
    boundaries = [position + 1 for position, char in enumerate(body) if char in ".!?…\n"]
    return min(boundaries) if boundaries else len(body)


def _event_start(event: CandidateEvent, facts: Mapping[str, EventFact], evidence: Mapping[str, EvidenceSpan]) -> int:
    if len(event.fact_ids) != 1:
        return 2**31 - 1
    fact = facts.get(event.fact_ids[0])
    if fact is None:
        return 2**31 - 1
    starts = [evidence[evidence_id].start for evidence_id in fact.evidence_ids if evidence_id in evidence]
    return min(starts) if starts else 2**31 - 1


def _title_binding(article: RawArticle, fact: EventFact) -> tuple[int, int]:
    title = _normalized(article.title).casefold()
    actor = _normalized(fact.subject).casefold()
    object_text = _normalized(fact.object or "").casefold()
    actor_bound = int(bool(actor) and actor in title)
    object_bound = int(bool(object_text) and object_text in title)
    return actor_bound, object_bound


def _centrality_rank(
    article: RawArticle,
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: MorphologyPort | None,
    lead_end: int,
) -> tuple[int, int, int, int, int]:
    fact = facts[event.fact_ids[0]]
    start = _event_start(event, facts, evidence)
    actor_bound, object_bound = _title_binding(article, fact)
    actor_specific = _actor_specificity(fact.subject, morphology)
    lead_bound = int(start < lead_end)
    # Specific named actors outrank generic/numeric actors. Among equally specific candidates,
    # source lead remains stronger than title substring binding, preserving ordinary news discourse.
    return (actor_specific, lead_bound, actor_bound, object_bound, -start)


def _historical_event_context(article: RawArticle, fact: EventFact) -> bool:
    """Return true only when a date-only event is clearly outside the source freshness horizon."""

    if fact.event_date is None or article.provenance.published_at is None:
        return False
    try:
        event_date = date.fromisoformat(fact.event_date)
    except ValueError:
        return False
    age_days = (article.provenance.published_at.date() - event_date).days
    # Date-only precision cannot establish an exact 72-hour boundary. Four or more calendar days
    # is therefore the first interval that is unambiguously older than the 72-hour source window.
    return age_days > 3


def assess_compatibility_article_understanding(
    article: RawArticle,
    *,
    events: tuple[CandidateEvent, ...],
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: MorphologyPort | None,
    now: datetime,
) -> dict[str, CompatibilityEventUnderstandingDecision]:
    """Jointly classify all extracted events from one article.

    At most one resolved event may remain PRIMARY. Centrality uses immutable source structure and
    morphology-derived actor specificity only; no generated text, verifier output, source/domain
    exception, or topic-specific vocabulary participates.
    """

    decisions = {
        event.event_id: assess_compatibility_event_understanding(
            event,
            facts=facts,
            evidence=evidence,
            morphology=morphology,
            now=now,
        )
        for event in events
    }

    for event in events:
        decision = decisions[event.event_id]
        if (
            decision.status is UnderstandingStatus.RESOLVED
            and decision.article_role is ArticleEventRole.PRIMARY
            and decision.publishable_event
            and len(event.fact_ids) == 1
        ):
            fact = facts.get(event.fact_ids[0])
            if fact is not None and _historical_event_context(article, fact):
                decisions[event.event_id] = CompatibilityEventUnderstandingDecision(
                    status=UnderstandingStatus.RESOLVED,
                    article_role=ArticleEventRole.CONTEXT,
                    topic_relation=TopicRelation.BACKGROUND,
                    publishable_event=False,
                    reasons=decision.reasons + ("historical_event_context",),
                )

    eligible = [
        event
        for event in events
        if decisions[event.event_id].status is UnderstandingStatus.RESOLVED
        and decisions[event.event_id].article_role is ArticleEventRole.PRIMARY
        and decisions[event.event_id].publishable_event
        and len(event.fact_ids) == 1
        and event.fact_ids[0] in facts
    ]
    if not eligible:
        return decisions

    lead_end = _first_sentence_end(article.body)
    ranked = sorted(
        eligible,
        key=lambda event: _centrality_rank(
            article,
            event,
            facts=facts,
            evidence=evidence,
            morphology=morphology,
            lead_end=lead_end,
        ),
        reverse=True,
    )
    winner = ranked[0]
    winner_rank = _centrality_rank(
        article,
        winner,
        facts=facts,
        evidence=evidence,
        morphology=morphology,
        lead_end=lead_end,
    )

    # A lead-bound explicit event is source-central by discourse position. Outside the lead, the
    # title must bind the specific actor itself; an object-only overlap can describe article context
    # without making that deep-body fact the source-central event. Generic/common-noun surfaces or
    # numeric counts must likewise not manufacture centrality from a shared headline noun. If the
    # compatibility extractor missed the true lead event, hold the article instead of promoting a
    # deep-body background fact.
    actor_specific, lead_bound, actor_bound, _object_bound, _ = winner_rank
    centrality_proven = bool(
        lead_bound
        or (actor_specific and actor_bound)
    )
    if not centrality_proven:
        for event in eligible:
            decisions[event.event_id] = CompatibilityEventUnderstandingDecision(
                status=UnderstandingStatus.UNRESOLVED,
                article_role=ArticleEventRole.CONTEXT,
                topic_relation=TopicRelation.UNRESOLVED,
                publishable_event=False,
                reasons=("article_centrality_unresolved",),
            )
        return decisions

    for event in eligible:
        if event.event_id == winner.event_id:
            continue
        decisions[event.event_id] = replace(
            decisions[event.event_id],
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=decisions[event.event_id].reasons + ("secondary_article_event",),
        )
    return decisions