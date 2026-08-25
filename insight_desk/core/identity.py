from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


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


_SUBJECT_TOKEN_RE = re.compile(r"[a-z][a-z0-9.+-]*|[가-힣]{2,}")
_SUBJECT_DESCRIPTOR_TOKENS = frozenset({"소속"})


def _subject_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in _SUBJECT_TOKEN_RE.findall(value)
        if token not in _SUBJECT_DESCRIPTOR_TOKENS
    )


def _subject_surface_compatible(left: str, right: str) -> bool:
    """Treat descriptor/orthography-only subject expansion as ambiguous, not a hard conflict.

    Phase 6 still receives evidence-bound subject surfaces rather than stable entity IDs. Tokenizing
    punctuation and parenthetical romanization lets forms such as ``SM 유니버스(Universe) 강사진``
    and ``SM Universe 소속 강사진`` reach the existing semantic same-event judgment. The helper
    never declares a merge by itself; genuinely different subject tokens remain a deterministic
    conflict.
    """

    left_tokens = _subject_tokens(left)
    right_tokens = _subject_tokens(right)
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
