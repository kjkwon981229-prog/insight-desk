from __future__ import annotations

"""Bounded source expansion for unresolved Canonical Event identity.

This lane is orchestration inside the Canonical Identity responsibility. It may acquire more source
material, but it never interprets raw article prose itself, never calls claim-verification providers,
and never converts missing evidence into a DIFFERENT_EVENT decision. Additional sources must first
pass through the shared Event Understanding owner and become ephemeral CanonicalEvent objects.
"""

from typing import Protocol

from insight_desk.core import CandidateEvent, CanonicalEvent, SourceDocument
from insight_desk.production_identity_core_v2 import CanonicalIdentityCore
from insight_desk.semantic.identity import SemanticIdentityJudgment


IDENTITY_RESOLUTION_DISCOVERY_LIMIT = 3
IDENTITY_RESOLUTION_ACQUISITION_LIMIT = 2


class CanonicalIdentityRegistry(Protocol):
    def canonical_event(self, event_id: str) -> CanonicalEvent: ...

    def source_for_event(self, event_id: str) -> SourceDocument: ...


class EventUnderstandingBridgePort(Protocol):
    def identity_bridge_events(
        self,
        article,
        *,
        topic_id: str,
    ) -> tuple[CanonicalEvent, ...]: ...


class DiscoveryPort(Protocol):
    def search(self, query: str, *, topic_id: str, limit: int = 10): ...


class AcquisitionPort(Protocol):
    def acquire(self, candidate): ...


def _unique_text(values: tuple[str | None, ...]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = " ".join(value.split()).strip()
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        output.append(text)
    return tuple(output)


class CanonicalIdentityResolutionLane:
    """Try one bounded source-expansion pass before an unresolved pair is held."""

    def __init__(
        self,
        registry: CanonicalIdentityRegistry,
        event_understanding_owner: EventUnderstandingBridgePort,
    ) -> None:
        self.registry = registry
        self.event_understanding_owner = event_understanding_owner

    def _query(self, left: CandidateEvent, right: CandidateEvent) -> str:
        left_event = self.registry.canonical_event(left.event_id)
        right_event = self.registry.canonical_event(right.event_id)
        common_actor = left_event.actor if left_event.actor.casefold() == right_event.actor.casefold() else None
        common_object = (
            left_event.object
            if left_event.object is not None
            and right_event.object is not None
            and left_event.object.casefold() == right_event.object.casefold()
            else None
        )
        common_time = left_event.event_time if left_event.event_time == right_event.event_time else None
        parts = _unique_text(
            (
                common_actor,
                common_object,
                common_time,
                left_event.actor,
                right_event.actor,
            )
        )
        return " ".join(parts[:4])

    def resolve(
        self,
        left: CandidateEvent,
        right: CandidateEvent,
        *,
        discovery: DiscoveryPort,
        acquisition: AcquisitionPort,
        topic_id: str,
    ) -> SemanticIdentityJudgment:
        left_source = self.registry.source_for_event(left.event_id)
        right_source = self.registry.source_for_event(right.event_id)
        left_event = self.registry.canonical_event(left.event_id)
        right_event = self.registry.canonical_event(right.event_id)
        identity = CanonicalIdentityCore(left_event, right_event)

        query = self._query(left, right)
        if not query:
            return SemanticIdentityJudgment(
                None,
                "canonical_identity_defer:resolution_query_unavailable",
                0,
                0,
            )

        try:
            candidates = discovery.search(
                query,
                topic_id=topic_id,
                limit=IDENTITY_RESOLUTION_DISCOVERY_LIMIT,
            )
        except Exception:
            return SemanticIdentityJudgment(
                None,
                "canonical_identity_defer:resolution_discovery_unavailable",
                0,
                0,
            )

        existing_urls = {left_source.url, right_source.url}
        acquisition_attempts = 0
        for candidate in candidates:
            if getattr(candidate, "url", None) in existing_urls:
                continue
            if acquisition_attempts >= IDENTITY_RESOLUTION_ACQUISITION_LIMIT:
                break
            acquisition_attempts += 1
            try:
                acquired = acquisition.acquire(candidate)
            except Exception:
                continue

            article = getattr(acquired, "article", None)
            if article is None:
                continue
            try:
                bridge_events = self.event_understanding_owner.identity_bridge_events(
                    article,
                    topic_id=topic_id,
                )
            except Exception:
                continue

            for bridge_event in bridge_events:
                if identity.bridge_corroborates_same_event(bridge_event):
                    return SemanticIdentityJudgment(
                        True,
                        "canonical_same_event:event_understanding_bridge",
                        0,
                        0,
                    )

        return SemanticIdentityJudgment(
            None,
            "canonical_identity_defer:bounded_source_expansion_exhausted",
            0,
            0,
        )
