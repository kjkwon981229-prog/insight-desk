from __future__ import annotations

"""Bounded evidence expansion for unresolved Event Understanding decisions.

The lane does not resolve or reclassify an event. It only requests a small amount of additional
source material. Any returned candidate must re-enter the normal Source -> Relevance -> Event
Understanding path before it can contribute a publishable event.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.core.event_understanding_v2 import UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import (
    CompatibilityEventUnderstandingDecision,
)


EVENT_UNDERSTANDING_RESOLUTION_DISCOVERY_LIMIT = 3


@dataclass(frozen=True, slots=True)
class EventUnderstandingSourceExpansion:
    decision: CompatibilityEventUnderstandingDecision
    attempted: bool
    candidates: tuple[Any, ...]
    reason: str


class BoundedEventUnderstandingSourceExpansionLane:
    """Collect source candidates for one unresolved understanding decision."""

    def __init__(self, *, candidate_limit: int = EVENT_UNDERSTANDING_RESOLUTION_DISCOVERY_LIMIT) -> None:
        if candidate_limit < 1:
            raise ValueError("candidate_limit must be positive")
        self.candidate_limit = candidate_limit

    def expand(
        self,
        *,
        decision: CompatibilityEventUnderstandingDecision,
        article: Any,
        event: CandidateEvent,
        facts: Mapping[str, EventFact],
        topic: Any,
        discovery: Any,
    ) -> EventUnderstandingSourceExpansion:
        if decision.status is not UnderstandingStatus.UNRESOLVED:
            return EventUnderstandingSourceExpansion(
                decision=decision,
                attempted=False,
                candidates=(),
                reason="event_understanding_defer:not_unresolved",
            )

        query = self._resolution_query(article=article, event=event, facts=facts, topic=topic)
        if query is None:
            return EventUnderstandingSourceExpansion(
                decision=decision,
                attempted=False,
                candidates=(),
                reason="event_understanding_defer:resolution_query_unavailable",
            )

        try:
            discovered = discovery.search(
                query,
                topic_id=str(topic.topic_id),
                limit=self.candidate_limit,
            )
        except Exception:
            return EventUnderstandingSourceExpansion(
                decision=decision,
                attempted=True,
                candidates=(),
                reason="event_understanding_defer:resolution_discovery_unavailable",
            )

        unique: list[Any] = []
        seen_urls: set[str] = set()
        for candidate in discovered:
            url = str(getattr(candidate, "url", "")).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique.append(candidate)
            if len(unique) >= self.candidate_limit:
                break

        return EventUnderstandingSourceExpansion(
            decision=decision,
            attempted=True,
            candidates=tuple(unique),
            reason="event_understanding_defer:source_expansion",
        )

    @staticmethod
    def _resolution_query(
        *,
        article: Any,
        event: CandidateEvent,
        facts: Mapping[str, EventFact],
        topic: Any,
    ) -> str | None:
        terms: list[str] = []
        seen: set[str] = set()

        def add(value: object) -> None:
            text = " ".join(str(value or "").split()).strip()
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                terms.append(text)

        # The source title is query context only; it is not semantic authority.
        add(getattr(article, "title", ""))
        for term in tuple(getattr(topic, "required_intent_terms", ())):
            add(term)
        for fact_id in event.fact_ids:
            fact = facts.get(fact_id)
            if fact is None:
                continue
            add(fact.subject)
            add(fact.action)
            add(fact.object)
            add(fact.event_date)

        if not terms:
            return None
        return " ".join(terms[:6])
