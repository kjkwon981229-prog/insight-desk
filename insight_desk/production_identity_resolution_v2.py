from __future__ import annotations

"""Bounded source expansion for unresolved Canonical Event identity.

This lane is orchestration inside the Canonical Identity responsibility. It may acquire more source
material, but it never calls claim-verification providers and never converts missing evidence into a
DIFFERENT_EVENT decision. A positive result requires one additional source to bridge both existing
events through source-backed identity evidence; otherwise the result remains DEFER.
"""

import hashlib
from typing import Protocol

from insight_desk.core import CandidateEvent, CanonicalEvent, SourceDocument
from insight_desk.semantic.identity import SemanticIdentityJudgment
from insight_desk.semantic.visible_identity import visible_event_redundant


IDENTITY_RESOLUTION_DISCOVERY_LIMIT = 3
IDENTITY_RESOLUTION_ACQUISITION_LIMIT = 2


class CanonicalIdentityRegistry(Protocol):
    def canonical_event(self, event_id: str) -> CanonicalEvent: ...

    def source_for_event(self, event_id: str) -> SourceDocument: ...


class DiscoveryPort(Protocol):
    def search(self, query: str, *, topic_id: str, limit: int = 10): ...


class AcquisitionPort(Protocol):
    def acquire(self, candidate): ...


def _normalized_source_digest(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _source_matches_event(*, topic_id: str, event_source: str, bridge_source: str) -> bool:
    if _normalized_source_digest(event_source) == _normalized_source_digest(bridge_source):
        return True
    return visible_event_redundant(
        topic_id=topic_id,
        prior_headline="",
        prior_summary="",
        candidate_headline="",
        candidate_summary="",
        prior_source_text=event_source,
        candidate_source_text=bridge_source,
    )


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

    def __init__(self, registry: CanonicalIdentityRegistry) -> None:
        self.registry = registry

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
                bridge_body = acquired.article.body
            except Exception:
                continue
            if not isinstance(bridge_body, str) or not bridge_body.strip():
                continue

            if _source_matches_event(
                topic_id=topic_id,
                event_source=left_source.body,
                bridge_source=bridge_body,
            ) and _source_matches_event(
                topic_id=topic_id,
                event_source=right_source.body,
                bridge_source=bridge_body,
            ):
                return SemanticIdentityJudgment(
                    True,
                    "canonical_same_event:bounded_source_bridge",
                    0,
                    0,
                )

        return SemanticIdentityJudgment(
            None,
            "canonical_identity_defer:bounded_source_expansion_exhausted",
            0,
            0,
        )
