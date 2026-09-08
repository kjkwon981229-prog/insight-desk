from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RelevanceVerdict(StrEnum):
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    DEFER = "defer"


class RelevanceReason(StrEnum):
    CONFIGURED_LITERAL_MATCH = "configured_literal_match"
    CONFIGURED_LITERAL_MISSING = "configured_literal_missing"
    RESOLUTION_REQUIRED = "resolution_required"


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    """Typed output of the one relevance owner.

    Relevance is tri-state. ``DEFER`` means the available source evidence is insufficient to
    resolve topic ownership; it must never be silently collapsed into ``IRRELEVANT``. Evidence
    references are optional during the compatibility migration because the preserved literal
    matcher does not yet emit canonical source ranges. Downstream code must not invent them.
    """

    topic_id: str
    verdict: RelevanceVerdict
    evidence_refs: tuple[str, ...]
    reasons: tuple[RelevanceReason, ...]

    def __post_init__(self) -> None:
        if not self.topic_id.strip():
            raise ValueError("relevance topic_id must be non-empty")
        if not self.reasons:
            raise ValueError("relevance decision requires at least one reason code")
        if self.verdict is RelevanceVerdict.DEFER and RelevanceReason.RESOLUTION_REQUIRED not in self.reasons:
            raise ValueError("deferred relevance must declare resolution_required")

    @property
    def is_relevant(self) -> bool:
        return self.verdict is RelevanceVerdict.RELEVANT

    @property
    def requires_resolution(self) -> bool:
        return self.verdict is RelevanceVerdict.DEFER


def relevance_from_literal_match(*, topic_id: str, matched: bool) -> RelevanceDecision:
    """Compatibility lift for the preserved configured-literal source matcher."""

    if matched:
        return RelevanceDecision(
            topic_id=topic_id,
            verdict=RelevanceVerdict.RELEVANT,
            evidence_refs=(),
            reasons=(RelevanceReason.CONFIGURED_LITERAL_MATCH,),
        )
    return RelevanceDecision(
        topic_id=topic_id,
        verdict=RelevanceVerdict.IRRELEVANT,
        evidence_refs=(),
        reasons=(RelevanceReason.CONFIGURED_LITERAL_MISSING,),
    )
