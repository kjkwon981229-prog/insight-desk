from __future__ import annotations

"""One fail-closed resolver for the production semantic authority.

The visible semantic authority is one exact byte range from one immutable SourceDocument. Owners
after Event Understanding may validate or route that proposition, but they may not reconstruct it
from actor/action/object fields or choose among several evidence spans.
"""

from dataclasses import dataclass
from typing import Protocol

from insight_desk.core import (
    CanonicalEvidenceRef,
    CanonicalEvent,
    ContractError,
    SourceDocument,
)


class CanonicalEventRegistry(Protocol):
    def canonical_event(self, event_id: str) -> CanonicalEvent: ...

    def source_for_event(self, event_id: str) -> SourceDocument: ...


@dataclass(frozen=True, slots=True)
class ExactCanonicalProposition:
    event: CanonicalEvent
    source: SourceDocument
    ref: CanonicalEvidenceRef
    text: str


def resolve_exact_canonical_proposition(
    registry: CanonicalEventRegistry,
    event_id: str,
) -> ExactCanonicalProposition:
    """Resolve exactly one canonical source proposition or fail closed."""

    event = registry.canonical_event(event_id)
    source = registry.source_for_event(event_id)
    if tuple(event.source_ids) != (source.source_id,):
        raise ContractError("canonical proposition requires one bound primary source")
    if len(event.evidence_refs) != 1:
        raise ContractError("canonical proposition requires exactly one evidence ref")

    ref = event.evidence_refs[0]
    ref.validate_against(source)
    source_text = source.title if ref.field == "title" else source.body
    proposition = source_text[ref.start : ref.end]
    if not proposition.strip():
        raise ContractError("canonical proposition must be non-empty")
    if "\n" in proposition or "\r" in proposition:
        raise ContractError("canonical proposition must stay within one source block")
    return ExactCanonicalProposition(
        event=event,
        source=source,
        ref=ref,
        text=proposition,
    )
