from __future__ import annotations

"""Bounded source expansion for unresolved event relevance.

This lane is orchestration, not a second relevance judge. A DEFER decision is preserved as DEFER;
the lane only requests a small number of additional discovery candidates derived from already
structured EventFact fields plus configured topic intent. Any returned source must enter the normal
Source -> Relevance -> Event Understanding pipeline from the beginning.
"""

from dataclasses import dataclass
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EventFact, RelevanceDecision


RELEVANCE_RESOLUTION_DISCOVERY_LIMIT = 3


class DiscoveryPort(Protocol):
    def search(self, query: str, *, topic_id: str, limit: int = 10): ...


class TopicPort(Protocol):
    topic_id: str
    required_intent_terms: tuple[str, ...]
    intent_anchors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RelevanceSourceExpansion:
    decision: RelevanceDecision
    candidates: tuple[object, ...]
    attempted: bool
    reason: str
    query: str | None = None


def _unique_text(values: tuple[str | None, ...]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = " ".join(value.split()).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(text)
    return tuple(output)


def _resolution_query(
    *,
    event: CandidateEvent,
    facts: Mapping[str, EventFact],
    topic: TopicPort,
) -> str | None:
    if len(event.fact_ids) != 1:
        return None
    fact = facts.get(event.fact_ids[0])
    if fact is None:
        return None

    configured_binding = tuple(topic.required_intent_terms) or tuple(topic.intent_anchors)
    binding = configured_binding[0] if configured_binding else None
    parts = _unique_text(
        (
            binding,
            fact.subject,
            fact.object,
            fact.action,
        )
    )
    return " ".join(parts[:4]) or None


class BoundedRelevanceSourceExpansionLane:
    """Request additional source candidates while preserving the original DEFER decision."""

    def expand(
        self,
        *,
        decision: RelevanceDecision,
        event: CandidateEvent,
        facts: Mapping[str, EventFact],
        topic: TopicPort,
        discovery: DiscoveryPort,
    ) -> RelevanceSourceExpansion:
        if not decision.requires_resolution:
            return RelevanceSourceExpansion(
                decision=decision,
                candidates=(),
                attempted=False,
                reason="relevance_defer:not_deferred",
            )

        query = _resolution_query(event=event, facts=facts, topic=topic)
        if query is None:
            return RelevanceSourceExpansion(
                decision=decision,
                candidates=(),
                attempted=False,
                reason="relevance_defer:resolution_query_unavailable",
            )

        try:
            discovered = discovery.search(
                query,
                topic_id=topic.topic_id,
                limit=RELEVANCE_RESOLUTION_DISCOVERY_LIMIT,
            )
        except Exception:
            return RelevanceSourceExpansion(
                decision=decision,
                candidates=(),
                attempted=True,
                reason="relevance_defer:resolution_discovery_unavailable",
                query=query,
            )

        candidates: list[object] = []
        seen_urls: set[str] = set()
        for candidate in discovered:
            url = str(getattr(candidate, "url", "") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(candidate)
            if len(candidates) >= RELEVANCE_RESOLUTION_DISCOVERY_LIMIT:
                break

        return RelevanceSourceExpansion(
            decision=decision,
            candidates=tuple(candidates),
            attempted=True,
            reason=(
                "relevance_defer:source_expansion"
                if candidates
                else "relevance_defer:bounded_source_expansion_exhausted"
            ),
            query=query,
        )
