from __future__ import annotations

"""Inactive production handoff for a future qualified Event Understanding owner.

This module does not select or call a provider. It accepts an already-produced
``ArticleUnderstanding``, mechanically validates exact source lineage, and promotes only resolved
``CanonicalEventDraft`` objects after Canonical Identity has supplied event ids. The current legacy
production semantic bridge remains active until the provider qualification and migration gates are
separately satisfied.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol

from insight_desk.core import CanonicalEvent, ContractError, SourceDocument
from insight_desk.core.event_understanding_port_v2 import (
    EventUnderstandingRequest,
    validate_understanding_result,
)
from insight_desk.core.event_understanding_v2 import (
    ArticleUnderstanding,
    UnderstandingStatus,
    canonical_event_from_draft,
)


class ProductionEventRegistry(Protocol):
    sources_by_article: dict[str, SourceDocument]
    events_by_id: dict[str, CanonicalEvent]


def _publication_time_for_sources(
    source_ids: tuple[str, ...],
    source_by_id: Mapping[str, SourceDocument],
) -> datetime | None:
    """Carry publication time only when every cited source agrees exactly."""

    values = tuple(source_by_id[source_id].publication_time for source_id in source_ids)
    if not values or values[0] is None:
        return None
    if any(value != values[0] for value in values[1:]):
        return None
    return values[0]


@dataclass(slots=True)
class ProductionEventUnderstandingHandoff:
    """Mechanically promote validated Event Understanding output into the production registry."""

    registry: ProductionEventRegistry

    def register(
        self,
        request: EventUnderstandingRequest,
        result: ArticleUnderstanding,
        *,
        event_ids: Mapping[str, str],
    ) -> tuple[CanonicalEvent, ...]:
        validate_understanding_result(request, result)
        if result.status is not UnderstandingStatus.RESOLVED:
            raise ContractError("unresolved understanding cannot enter production handoff")

        draft_ids = tuple(draft.draft_id for draft in result.event_drafts)
        if set(event_ids) != set(draft_ids):
            raise ContractError("event-id assignments must exactly match resolved event drafts")
        assigned_ids = tuple(event_ids[draft_id] for draft_id in draft_ids)
        if any(not event_id.strip() for event_id in assigned_ids):
            raise ContractError("assigned canonical event ids must be non-empty")
        if len(assigned_ids) != len(set(assigned_ids)):
            raise ContractError("assigned canonical event ids must be unique")

        source_by_id = {source.source_id: source for source in request.sources}
        promoted = tuple(
            canonical_event_from_draft(
                draft,
                event_id=event_ids[draft.draft_id],
                publication_time=_publication_time_for_sources(draft.source_ids, source_by_id),
            )
            for draft in result.event_drafts
        )

        # Validate all conflicts before mutating the registry so a rejected handoff is atomic.
        for event in promoted:
            existing = self.registry.events_by_id.get(event.event_id)
            if existing is not None and existing != event:
                raise ContractError(f"conflicting canonical event id: {event.event_id}")
        for source in request.sources:
            for candidate_id in source.candidate_ids:
                existing = self.registry.sources_by_article.get(candidate_id)
                if existing is not None and existing != source:
                    raise ContractError(f"conflicting source candidate id: {candidate_id}")

        for source in request.sources:
            for candidate_id in source.candidate_ids:
                self.registry.sources_by_article[candidate_id] = source
        for event in promoted:
            self.registry.events_by_id[event.event_id] = event
        return promoted
