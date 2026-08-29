from __future__ import annotations

"""Execution-scoped relevance owner for the Phase 4 production migration."""

from collections.abc import Callable
from dataclasses import dataclass

from insight_desk.core import RelevanceDecision, relevance_from_literal_match


@dataclass(frozen=True, slots=True)
class ConfiguredLiteralRelevanceOwner:
    """Lift the preserved source matcher into the typed relevance contract.

    This owner intentionally does not add new semantic heuristics. The legacy configured-literal
    matcher remains the current evidence signal until a qualified semantic relevance resolver is
    introduced. The important migration property is that downstream production consumes a typed
    tri-state contract rather than a bare boolean.
    """

    matcher: Callable[..., bool]

    def decide(self, *, title: str, body: str, topic) -> RelevanceDecision:
        matched = self.matcher(title=title, body=body, topic=topic)
        return relevance_from_literal_match(topic_id=topic.topic_id, matched=matched)
