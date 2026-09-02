from __future__ import annotations

"""Execution-scoped relevance owner for the Phase 4/7 production migration."""

from collections.abc import Callable
from contextvars import ContextVar
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


_EVENT_RELEVANCE_AUDIT: ContextVar[RelevanceDecision | None] = ContextVar(
    "insight_desk_event_relevance_audit",
    default=None,
)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _term_present(text: str, term: str) -> bool:
    value = _normalized(term)
    return bool(value) and value.casefold() in _normalized(text).casefold()


def _fact_surface(fact: EventFact) -> str:
    return " ".join(value for value in (fact.subject, fact.action, fact.object or "") if value)


def _term_is_direct_in_action(action: str, term: str, morphology: MorphologyPort | None) -> bool | None:
    """Resolve whether a configured event term belongs to the event-bearing clause."""

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
    while True:
        start = folded.find(needle, cursor)
        if start < 0:
            return False
        end = start + len(needle)
        cursor = max(end, start + 1)
        following = next(
            (token for token in tokens if int(getattr(token, "start", -1)) >= end),
            None,
        )
        # A noun used only as a genitive modifier (e.g. ``시험의 인기``) is background context,
        # not the event-bearing topic predicate.
        if following is not None and str(getattr(following, "tag", "")) == "JKG":
            continue
        return True


def event_relevance_decision(
    *,
    event: CandidateEvent,
    facts: Mapping[str, EventFact],
    topic,
    morphology: MorphologyPort | None,
) -> RelevanceDecision:
    """Resolve event-level direct topic ownership after source-level relevance has passed."""

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
    required_terms = tuple(dict.fromkeys(tuple(topic.required_intent_terms)))
    binding_terms = required_terms or tuple(dict.fromkeys(tuple(topic.intent_anchors)))
    if binding_terms and not any(_term_present(surface, term) for term in binding_terms):
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=fact.evidence_ids,
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )

    for term in tuple(topic.event_terms):
        if _term_present(fact.subject, term) or _term_present(fact.object or "", term):
            return RelevanceDecision(
                topic_id=topic.topic_id,
                verdict=RelevanceVerdict.RELEVANT,
                evidence_refs=fact.evidence_ids,
                reasons=(RelevanceReason.CONFIGURED_LITERAL_MATCH,),
            )
        relation = _term_is_direct_in_action(fact.action, term, morphology)
        if relation is True:
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


def project_event_relevance(decision: RelevanceDecision) -> bool:
    """Compatibility bool projection that preserves the typed decision for the next audit write."""

    _EVENT_RELEVANCE_AUDIT.set(decision if decision.requires_resolution else None)
    return decision.is_relevant


def rewrite_event_relevance_attempt(
    *,
    stage: str,
    status: str,
    reason: str | None,
) -> tuple[str, str | None]:
    """Preserve DEFER in the legacy mechanical loop's audit surface.

    This function does not make a semantic decision. It consumes the decision already produced by
    the relevance owner and rewrites only the immediately following compatibility audit projection.
    """

    if stage != "event_topic_relevance":
        return status, reason
    decision = _EVENT_RELEVANCE_AUDIT.get()
    _EVENT_RELEVANCE_AUDIT.set(None)
    if decision is not None and decision.verdict is RelevanceVerdict.DEFER:
        return "defer", RelevanceReason.RESOLUTION_REQUIRED.value
    return status, reason


@dataclass(frozen=True, slots=True)
class ConfiguredLiteralRelevanceOwner:
    """Single compatibility owner for source and event relevance decisions."""

    matcher: Callable[..., bool]
    morphology: MorphologyPort | None = None

    def decide(self, *, title: str, body: str, topic) -> RelevanceDecision:
        matched = self.matcher(title=title, body=body, topic=topic)
        return relevance_from_literal_match(topic_id=topic.topic_id, matched=matched)

    def decide_canonical_proposition(
        self,
        *,
        proposition: str,
        canonical_topic: str,
        topic,
        evidence_refs: tuple[str, ...] = (),
    ) -> RelevanceDecision:
        """Bind the selected event to its topic using only its exact source proposition.

        Article-level relevance may be satisfied by terms scattered across unrelated source
        blocks. Once Event Understanding has selected the central event, topic ownership must be
        proved locally by the same immutable proposition that can become visible. Flat
        actor/action/object fields are deliberately not consulted.
        """

        binding_terms = tuple(
            dict.fromkeys(
                tuple(topic.required_intent_terms)
                + tuple(topic.intent_anchors)
            )
        )
        if canonical_topic != topic.topic_id or not binding_terms:
            matched = False
        else:
            proposition_topic = _CanonicalPropositionTopic(
                topic_id=topic.topic_id,
                intent_anchors=binding_terms,
                required_intent_terms=(),
            )
            matched = self.matcher(
                title=proposition,
                body="",
                topic=proposition_topic,
            )

        if matched:
            return RelevanceDecision(
                topic_id=topic.topic_id,
                verdict=RelevanceVerdict.RELEVANT,
                evidence_refs=evidence_refs,
                reasons=(RelevanceReason.CONFIGURED_LITERAL_MATCH,),
            )
        return RelevanceDecision(
            topic_id=topic.topic_id,
            verdict=RelevanceVerdict.DEFER,
            evidence_refs=evidence_refs,
            reasons=(RelevanceReason.RESOLUTION_REQUIRED,),
        )

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

    def project_event(
        self,
        *,
        event: CandidateEvent,
        facts: Mapping[str, EventFact],
        topic,
    ) -> bool:
        return project_event_relevance(
            self.decide_event(event=event, facts=facts, topic=topic)
        )


@dataclass(frozen=True, slots=True)
class _CanonicalPropositionTopic:
    """Minimal topic surface consumed by the preserved configured-literal matcher."""

    topic_id: str
    intent_anchors: tuple[str, ...]
    required_intent_terms: tuple[str, ...]
