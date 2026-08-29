from __future__ import annotations

"""Execution-scoped relevance owner for the Phase 4/7 production migration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Mapping, Protocol

from insight_desk.core import (
    CandidateEvent,
    EventFact,
    RelevanceDecision,
    RelevanceReason,
    RelevanceVerdict,
    relevance_from_literal_match,
)


class MorphologyPort(Protocol):
    def analyze(self, text: str): ...


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _term_present(text: str, term: str) -> bool:
    value = _normalized(term)
    return bool(value) and value.casefold() in _normalized(text).casefold()


def _fact_surface(fact: EventFact) -> str:
    return " ".join(value for value in (fact.subject, fact.action, fact.object or "") if value)


def _term_is_direct_in_action(action: str, term: str, morphology: MorphologyPort | None) -> bool | None:
    """Resolve whether a configured event term belongs to the event-bearing clause.

    A configured event noun used only as a Korean genitive modifier (``... 시험의 인기``) is
    contextual evidence, not the event predicate itself. Morphology is used only to distinguish
    this grammatical relation; no topic-specific vocabulary is introduced here.
    """

    if not _term_present(action, term):
        return False
    if morphology is None:
        return None
    try:
        tokens = tuple(morphology.analyze(action))
    except Exception:
        return None
    if not tokens:
        return None

    folded = action.casefold()
    needle = _normalized(term).casefold()
    cursor = 0
    saw_occurrence = False
    while True:
        start = folded.find(needle, cursor)
        if start < 0:
            break
        saw_occurrence = True
        end = start + len(needle)
        cursor = max(end, start + 1)
        following = next((token for token in tokens if int(getattr(token, "start", -1)) >= end), None)
        if following is not None and str(getattr(following, "tag", "")) == "JKG":
            continue
        return True
    return False if saw_occurrence else False


def event_relevance_decision(
    *,
    event: CandidateEvent,
    facts: Mapping[str, EventFact],
    topic,
    morphology: MorphologyPort | None,
) -> RelevanceDecision:
    """Resolve event-level direct topic ownership after source-level relevance has passed.

    The source matcher answers whether an article is worth semantic extraction. This owner answers
    the narrower question: is this extracted EventFact itself a direct event for that configured
    topic? Ambiguous grammatical binding remains DEFER; it is never collapsed into IRRELEVANT.
    """

    if event.topic_id != topic.topic_id or len(event.fact_ids) != 1:
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=(),
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )
    fact = facts.get(event.fact_ids[0])
    if fact is None:
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=(),
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )

    surface = _fact_surface(fact)
    topic_terms = tuple(dict.fromkeys(tuple(topic.intent_anchors) + tuple(topic.required_intent_terms)))
    if topic_terms and not any(_term_present(surface, term) for term in topic_terms):
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=fact.evidence_ids,
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )

    direct = False
    unresolved = False
    for term in tuple(topic.event_terms):
        if _term_present(fact.subject, term) or _term_present(fact.object or "", term):
            direct = True
            break
        relation = _term_is_direct_in_action(fact.action, term, morphology)
        if relation is True:
            direct = True
            break
        if relation is None and _term_present(fact.action, term):
            unresolved = True

    if direct:
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.RELEVANT,
            evidence_refs=fact.evidence_ids,
            reasons=(RelevanceReason.CONFIGURED_LITERAL_MATCH,),
        )

    return RelevanceDecision(
        topic_id=topic.topic_id,
        verdict=RelevanceVerdict.DEFER,
        evidence_refs=fact.evidence_ids,
        reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
    )


@dataclass(frozen=True, slots=True)
class ConfiguredLiteralRelevanceOwner:
    """Single compatibility owner for source and event relevance decisions."""

    matcher: Callable[..., bool]
    morphology: MorphologyPort | None = None

    def decide(self, *, title: str, body: str, topic) -> RelevanceDecision:
        matched = self.matcher(title=title, body=body, topic=topic)
        return relevance_from_literal_match(topic_id=topic.topic_id, matched=matched)

    def decide_event(
        self,
        *,
        event: CandidateEvent,
        facts: Mapping[str, EventFact],
        topic,
    ) -> RelevanceDecision:
        return event_relevance_decision(
            event=event,
            facts=facts,
            topic=topic,
            morphology=self.morphology,
        )
