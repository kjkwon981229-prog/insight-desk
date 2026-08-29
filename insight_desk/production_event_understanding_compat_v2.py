from __future__ import annotations

"""Bounded Event Understanding compatibility owner for the legacy extraction bridge.

This module is deliberately provider-free. It does not create CanonicalEvent objects and it does
not replace the qualified Event Understanding provider contract. It classifies the already
extracted, evidence-bound CandidateEvents jointly at article scope so the production loop can
separate one source-central news event from contextual/analytical facts before Phase 6 selection.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, RawArticle
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

    This is the local semantic primitive used by the article-level owner. Production should consume
    ``assess_compatibility_article_understanding`` so centrality is decided jointly, not one fact at
    a time. ``now`` is explicit for parity with the future Event Understanding boundary; it is not
    used to reinterpret evidence here.
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


def _first_sentence_end(body: str) -> int:
    """Return the exact source boundary of the first lead sentence/line.

    Centrality uses source discourse structure, not a topic-specific character threshold. The first
    sentence terminator or physical line break is the lead boundary; if neither exists, the entire
    body is one lead sentence.
    """

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
    lead_end: int,
) -> tuple[int, int, int, int]:
    fact = facts[event.fact_ids[0]]
    start = _event_start(event, facts, evidence)
    actor_bound, object_bound = _title_binding(article, fact)
    lead_bound = int(start < lead_end)
    # Lead position is the strongest compatibility signal. Title-bound actor/object breaks ties,
    # then exact source order provides a deterministic final choice.
    return (lead_bound, actor_bound, object_bound, -start)


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

    The legacy extractor deliberately emits one CandidateEvent per fact. Treating every individually
    valid fact as PRIMARY leaks lineups, historical statistics, marketing metrics, and other body
    context into publication. This compatibility owner therefore performs one bounded source-
    centrality decision across the article: at most one resolved event may remain PRIMARY.

    Centrality is based only on immutable source structure already available to Event Understanding:
    exact evidence position plus actor/object binding to the source title. No generated text,
    verifier output, topic-specific source/domain rule, or publication surface participates.
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
        lead_end=lead_end,
    )

    # If no candidate is tied to either the lead sentence or the title, the compatibility bridge
    # cannot prove article centrality. Fail closed instead of promoting an arbitrary deep-body fact.
    if winner_rank[:3] == (0, 0, 0):
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
