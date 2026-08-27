from __future__ import annotations

"""Provider-agnostic port for the V2 Event Understanding owner.

This module defines only the semantic request/response boundary and mechanical provenance checks.
It does not select a model, call a provider, classify topic keywords, or implement uncertainty
resolution.
"""

from dataclasses import dataclass
from typing import Protocol

from .canonical_v2 import SourceDocument
from .contracts import ContractError
from .event_understanding_v2 import ArticleUnderstanding


@dataclass(frozen=True, slots=True)
class EventUnderstandingRequest:
    topic: str
    sources: tuple[SourceDocument, ...]

    def __post_init__(self) -> None:
        if not self.topic.strip():
            raise ContractError("event-understanding topic must be non-empty")
        if not self.sources:
            raise ContractError("event understanding requires at least one SourceDocument")
        source_ids = tuple(source.source_id for source in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ContractError("event-understanding source ids must be unique")

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources)


class EventUnderstandingPort(Protocol):
    engine_id: str

    def understand(self, request: EventUnderstandingRequest) -> ArticleUnderstanding: ...


def validate_understanding_result(
    request: EventUnderstandingRequest,
    result: ArticleUnderstanding,
) -> None:
    """Mechanically bind semantic output to its exact request sources.

    This validates only contract lineage: topic, source membership, source ranges, and byte digests.
    It does not judge whether the semantic interpretation itself is correct.
    """

    if result.topic != request.topic:
        raise ContractError("understanding topic differs from request topic")

    request_sources = {source.source_id: source for source in request.sources}
    if not set(result.source_ids).issubset(request_sources):
        raise ContractError("understanding references a source outside the request")

    for draft in result.event_drafts:
        if not set(draft.source_ids).issubset(request_sources):
            raise ContractError(f"{draft.draft_id}: draft references a source outside the request")
        for evidence_ref in draft.evidence_refs:
            source = request_sources.get(evidence_ref.source_id)
            if source is None:
                raise ContractError(
                    f"{draft.draft_id}: evidence references a source outside the request"
                )
            evidence_ref.validate_against(source)
