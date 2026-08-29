from __future__ import annotations

"""Canonical-only production event identity decisions.

This owner consumes only ``CanonicalEvent`` semantics. It does not inspect article bodies, generated
headline/summary text, legacy CandidateEvent facts, or claim-verification providers. Explicit
canonical conflicts are deterministic blocks; narrow parent relationships may resolve locally; all
other ambiguity remains DEFER for the bounded source-resolution lane.
"""

from dataclasses import dataclass

from insight_desk.core import CanonicalEvent, IdentityDecision, IdentityKey
from insight_desk.core.identity import finalize_identity, precheck_identity
from insight_desk.semantic.baseball_identity import same_game_result_fingerprint
from insight_desk.semantic.market_identity import same_market_session_fact_perspective


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split()).casefold()
    return value or None


def _event_surface(event: CanonicalEvent) -> str:
    return " ".join(
        value
        for value in (
            event.actor,
            event.action,
            event.object or "",
            " ".join(event.participants),
            event.metric or "",
            event.value or "",
            event.unit or "",
            event.location or "",
        )
        if value
    )


def _identity_key(event: CanonicalEvent) -> IdentityKey:
    return IdentityKey(
        subject_key=_normalized(event.actor),
        action_key=_normalized(event.action),
        object_key=_normalized(event.object),
        event_date_key=_normalized(event.event_time),
        location_key=_normalized(event.location),
        cause_key=_normalized(event.cause),
    )


def _without_subject(key: IdentityKey) -> IdentityKey:
    return IdentityKey(
        subject_key=None,
        action_key=key.action_key,
        object_key=key.object_key,
        event_date_key=key.event_date_key,
        location_key=key.location_key,
        cause_key=key.cause_key,
    )


def _explicit_day_markers(event: CanonicalEvent) -> frozenset[int]:
    """Read explicit Korean day-of-month markers from canonical fields only.

    The legacy bridge may leave ``event_time`` unresolved while preserving a literal schedule such
    as ``27일`` inside ``CanonicalEvent.action``. This is a bounded structural fallback for identity,
    not a source-text detector: raw article bytes are never consulted.
    """

    surface = " ".join(value for value in (event.action, event.object or "") if value)
    for punctuation in "()[]{}<>,.;:!?/\\\"'‘’“”·":
        surface = surface.replace(punctuation, " ")
    markers: set[int] = set()
    for token in surface.split():
        if not token.endswith("일"):
            continue
        number = token[:-1]
        if number.isdigit():
            day = int(number)
            if 1 <= day <= 31:
                markers.add(day)
    return frozenset(markers)


def _same_schedule_anchor(left: CanonicalEvent, right: CanonicalEvent) -> bool:
    if left.event_time is not None or right.event_time is not None:
        return bool(left.event_time and left.event_time == right.event_time)
    left_days = _explicit_day_markers(left)
    right_days = _explicit_day_markers(right)
    return bool(left_days and right_days and left_days.intersection(right_days))


def _same_structured_bok_policy_meeting(left: CanonicalEvent, right: CanonicalEvent) -> bool:
    if left.topic != "economy" or right.topic != "economy":
        return False
    if not _same_schedule_anchor(left, right):
        return False

    def actor_is_bok(event: CanonicalEvent) -> bool:
        actor_surface = " ".join((event.actor, *event.participants))
        return any(
            token in actor_surface
            for token in ("한국은행", "금융통화위원회", "한은", "금통위")
        )

    def is_rate_decision(event: CanonicalEvent) -> bool:
        decision_surface = " ".join(value for value in (event.action, event.object or "") if value)
        return (
            actor_is_bok(event)
            and any(token in decision_surface for token in ("기준금리", "정책금리"))
            and "결정" in event.action
        )

    def is_policy_meeting_output(event: CanonicalEvent) -> bool:
        if not actor_is_bok(event):
            return False
        surface = " ".join(value for value in (event.action, event.object or "") if value)
        policy_output = any(
            token in surface
            for token in (
                "기준금리",
                "정책금리",
                "수정 경제전망",
                "경제전망",
                "성장률 전망",
                "물가 전망",
                "점도표",
                "금리 전망",
            )
        )
        meeting_action = any(token in event.action for token in ("결정", "공개", "발표", "전망"))
        return policy_output and meeting_action

    return (
        is_rate_decision(left) and is_policy_meeting_output(right)
    ) or (
        is_rate_decision(right) and is_policy_meeting_output(left)
    )


@dataclass(frozen=True, slots=True)
class CanonicalIdentityCore:
    left: CanonicalEvent
    right: CanonicalEvent

    def precheck(self, *, semantic_same_event: bool | None = None) -> IdentityDecision:
        if self.left.topic != self.right.topic:
            return IdentityDecision(
                same_event=False,
                deterministic_block=True,
                llm_judgment_used=False,
                reason="canonical_identity_conflict:topic",
            )

        left_key = _identity_key(self.left)
        right_key = _identity_key(self.right)
        left_surface = _event_surface(self.left)
        right_surface = _event_surface(self.right)

        # Preserve the two historical perspective relaxations, but compute them only from canonical
        # structured fields rather than raw source prose or CandidateEvent/EventFact objects.
        if self.left.topic == "kbo_hanwha" and same_game_result_fingerprint(
            left_surface,
            right_surface,
        ):
            left_key = _without_subject(left_key)
            right_key = _without_subject(right_key)
        if self.left.topic == "economy" and same_market_session_fact_perspective(
            left_subject=self.left.actor,
            right_subject=self.right.actor,
            left_text=left_surface,
            right_text=right_surface,
            left_date=self.left.event_time,
            right_date=self.right.event_time,
        ):
            left_key = _without_subject(left_key)
            right_key = _without_subject(right_key)

        return finalize_identity(
            precheck_identity(left_key, right_key),
            llm_same_event=semantic_same_event,
        )

    @property
    def same_structured_bok_policy_meeting(self) -> bool:
        return _same_structured_bok_policy_meeting(self.left, self.right)
