from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SelectionVerdict(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    DEFER = "defer"


class SelectionReason(StrEnum):
    ELIGIBLE = "eligible"
    TOPIC_IRRELEVANT = "topic_irrelevant"
    NOT_MATERIAL = "not_material"
    STALE = "stale"
    SOURCE_UNUSABLE = "source_unusable"
    NO_VERIFIED_CLAIM = "no_verified_claim"
    IDENTITY_UNRESOLVED = "identity_unresolved"
    SEMANTIC_SIGNAL_MISSING = "semantic_signal_missing"


@dataclass(frozen=True, slots=True)
class SelectionSignals:
    """Explicit inputs to business selection; this object performs no text interpretation."""

    topic_relevant: bool | None
    material_event: bool | None
    fresh: bool | None
    source_usable: bool | None
    identity_resolved: bool
    verified_claim_count: int

    def __post_init__(self) -> None:
        if self.verified_claim_count < 0:
            raise ValueError("verified_claim_count must be >= 0")


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    verdict: SelectionVerdict
    reasons: tuple[SelectionReason, ...]


def decide_selection(signals: SelectionSignals) -> SelectionDecision:
    """Apply explicit briefing policy without rewriting semantic facts.

    `material_event=True` can still be excluded for relevance/freshness/source reasons. Conversely,
    exclusion never mutates the underlying event into a non-event. Unknown semantic signals defer
    rather than inventing a negative label.
    """

    exclusions: list[SelectionReason] = []
    if signals.topic_relevant is False:
        exclusions.append(SelectionReason.TOPIC_IRRELEVANT)
    if signals.material_event is False:
        exclusions.append(SelectionReason.NOT_MATERIAL)
    if signals.fresh is False:
        exclusions.append(SelectionReason.STALE)
    if signals.source_usable is False:
        exclusions.append(SelectionReason.SOURCE_UNUSABLE)
    if exclusions:
        return SelectionDecision(SelectionVerdict.EXCLUDE, tuple(exclusions))

    if None in (
        signals.topic_relevant,
        signals.material_event,
        signals.fresh,
        signals.source_usable,
    ):
        return SelectionDecision(
            SelectionVerdict.DEFER,
            (SelectionReason.SEMANTIC_SIGNAL_MISSING,),
        )
    if not signals.identity_resolved:
        return SelectionDecision(
            SelectionVerdict.DEFER,
            (SelectionReason.IDENTITY_UNRESOLVED,),
        )
    if signals.verified_claim_count == 0:
        return SelectionDecision(
            SelectionVerdict.DEFER,
            (SelectionReason.NO_VERIFIED_CLAIM,),
        )
    return SelectionDecision(SelectionVerdict.INCLUDE, (SelectionReason.ELIGIBLE,))
