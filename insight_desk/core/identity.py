from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IdentityPrecheckVerdict(StrEnum):
    BLOCK_MERGE = "block_merge"
    REQUIRE_LLM_JUDGMENT = "require_llm_judgment"


@dataclass(frozen=True, slots=True)
class IdentityKey:
    """Canonical identity attributes produced upstream from explicit evidence.

    Values here are canonical keys, not raw article phrases. This module performs no synonym,
    entity, or temporal NLP. Missing values are allowed; conflicting canonical values are not
    silently reconciled.
    """

    subject_key: str | None = None
    action_key: str | None = None
    object_key: str | None = None
    event_date_key: str | None = None
    location_key: str | None = None
    cause_key: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityPrecheck:
    verdict: IdentityPrecheckVerdict
    matching_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    same_event: bool
    deterministic_block: bool
    llm_judgment_used: bool
    reason: str


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized or None


def _subject_surface_compatible(left: str, right: str) -> bool:
    """Treat descriptor-only subject expansion as ambiguous, not as an explicit entity conflict.

    Phase 6 currently receives evidence-bound surface subjects rather than a stable entity ID.
    If every token from one subject also appears in the other, the difference is compatible with
    an added descriptor (for example ``공간 ax 기업 hdc랩스`` versus
    ``공간 ax 솔루션 기업 hdc랩스``). Such pairs still require downstream semantic same-event
    verification; this helper never declares a merge by itself.
    """

    left_tokens = frozenset(left.split())
    right_tokens = frozenset(right.split())
    if not left_tokens or not right_tokens:
        return False
    return left_tokens <= right_tokens or right_tokens <= left_tokens


def precheck_identity(left: IdentityKey, right: IdentityKey) -> IdentityPrecheck:
    """Block only explicit canonical conflicts; otherwise require an LLM identity judgment.

    The deterministic layer is deliberately conservative. It never declares two records the same
    event by itself. A merge always requires an explicit downstream same-event judgment.
    """

    matching: list[str] = []
    conflicts: list[str] = []

    values = {
        "subject": (left.subject_key, right.subject_key),
        "action": (left.action_key, right.action_key),
        "object": (left.object_key, right.object_key),
        "event_date": (left.event_date_key, right.event_date_key),
        "location": (left.location_key, right.location_key),
        "cause": (left.cause_key, right.cause_key),
    }
    for name, (left_value, right_value) in values.items():
        left_normalized = _normalized(left_value)
        right_normalized = _normalized(right_value)
        if left_normalized is None or right_normalized is None:
            continue
        if left_normalized == right_normalized:
            matching.append(name)
        elif name == "subject" and _subject_surface_compatible(
            left_normalized,
            right_normalized,
        ):
            continue
        elif name in {"subject", "event_date", "location", "cause"}:
            conflicts.append(name)

    verdict = (
        IdentityPrecheckVerdict.BLOCK_MERGE
        if conflicts
        else IdentityPrecheckVerdict.REQUIRE_LLM_JUDGMENT
    )
    return IdentityPrecheck(
        verdict=verdict,
        matching_fields=tuple(matching),
        conflicting_fields=tuple(conflicts),
    )


def finalize_identity(
    precheck: IdentityPrecheck,
    *,
    llm_same_event: bool | None,
) -> IdentityDecision:
    """Combine deterministic conflicts with an explicit LLM judgment.

    Missing/failed LLM judgment always fails safe by keeping the candidate events separate.
    No LLM result can override an explicit canonical conflict.
    """

    if precheck.verdict is IdentityPrecheckVerdict.BLOCK_MERGE:
        return IdentityDecision(
            same_event=False,
            deterministic_block=True,
            llm_judgment_used=False,
            reason="canonical_identity_conflict:" + ",".join(precheck.conflicting_fields),
        )
    if llm_same_event is True:
        return IdentityDecision(
            same_event=True,
            deterministic_block=False,
            llm_judgment_used=True,
            reason="llm_same_event_with_no_deterministic_conflict",
        )
    if llm_same_event is False:
        return IdentityDecision(
            same_event=False,
            deterministic_block=False,
            llm_judgment_used=True,
            reason="llm_different_event",
        )
    return IdentityDecision(
        same_event=False,
        deterministic_block=False,
        llm_judgment_used=False,
        reason="identity_judgment_unavailable_keep_separate",
    )
