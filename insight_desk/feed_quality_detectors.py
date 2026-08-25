from __future__ import annotations

from datetime import datetime
import re

# Low-level story-quality detectors live here. They expose individual signals only;
# admission policy composition belongs exclusively to story_admission.py.
from insight_desk.feed_quality_detectors_core import *  # noqa: F401,F403
from insight_desk.feed_quality_detectors_core import (
    non_event_analytical_text as _core_non_event_analytical_text,
    stale_day_only_context as _core_stale_day_only_context,
    stale_explicit_past_event_text as _core_stale_explicit_past_event_text,
    stale_quarter_context as _core_stale_quarter_context,
    stale_relative_past_event_text as _core_stale_relative_past_event_text,
    stale_relative_period_event_text as _core_stale_relative_period_event_text,
)


_CURRENT_WEEK_AGGREGATE_CUES = (
    "집계",
    "평균",
    "경기 시간",
    "10개 구단",
    "가장 길",
    "가장 짧",
    "주간 통계",
    "주간 기록",
)
_PRIOR_PERIOD_POLICY_EVENT_RE = re.compile(
    r"(?:지난달|지난\s+달|지난\s+분기|지난\s+연도)"
    r"[^!?。！？]{0,180}?(?:기준금리|정책금리|금리)"
    r"[^!?。！？]{0,120}?(?:올렸|내렸|인상했|인하했|동결했)"
)
_PUBLISHER_NOTICE_PERMISSION_CUES = ("무단", "사전허가없이", "사전 허가 없이")
_PUBLISHER_NOTICE_RESTRICTION_TERMS = ("복사", "배포", "전재", "재배포", "판매")
_PUBLISHER_NOTICE_LEGAL_CUES = ("책임", "금지", "저작권")
_SPORTS_CONTEXT_CUES = ("경기에서", "전에서", "경기 중", "경기에")
_SPORTS_DEPICTIVE_ACTION_CUES = (
    "투구",
    "타격",
    "수비",
    "훈련",
    "캐치볼",
    "몸을 풀",
    "세리머니",
    "포즈",
)
_SPORTS_DEPICTIVE_ENDINGS = ("고 있다", "고 있다.", "고 있습니다", "고 있습니다.")

_PRIMARY_CURRENT_EVENT_CUES = (
    "발표",
    "공개",
    "출시",
    "도입",
    "시행",
    "개정",
    "변경",
    "확정",
    "결정",
    "체결",
    "유치",
    "투자",
    "인수",
    "선발",
    "접수",
    "합격",
    "수상",
    "공연",
    "개최",
    "실시",
    "진행",
    "기록",
    "조사",
    "응답",
    "상승",
    "하락",
    "증가",
    "감소",
)
_PRIMARY_GOAL_RE = re.compile(
    r"(?:목표|목적|지향점|방향)(?:으?로)?[^.!?。！？]{0,24}?(?:한다|삼는다|두고\s*있다|이다)$"
)
_PRIMARY_NORMATIVE_ENDINGS = (
    "해야 한다",
    "하여야 한다",
    "충족해야 한다",
    "적용해야 한다",
    "필요하다",
    "요구된다",
    "준수해야 한다",
)
_PRIMARY_ANALYTICAL_CUES = (
    "시각이 우세",
    "견해가 우세",
    "의견이 우세",
    "의견도 맞서",
    "의견이 맞서",
    "견해가 맞서",
    "전망이 엇갈",
    "의견이 엇갈",
    "견해가 엇갈",
    "논쟁",
)
_PRIMARY_ABSTRACT_RESPONSE_CUES = ("변화", "체계", "환경", "상황", "흐름")
_PRIMARY_RESPONSE_ENDINGS = (
    "대응한다",
    "대응하고 있다",
    "대응하고 있습니다",
    "선제적으로 대응한다",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _primary_sentence(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""
    for sentence in _SENTENCE_SPLIT_RE.split(normalized):
        sentence = sentence.strip()
        if sentence:
            return sentence
    return normalized


def _has_primary_current_event(value: str) -> bool:
    return any(cue in value for cue in _PRIMARY_CURRENT_EVENT_CUES)


def _primary_non_event_state(value: str) -> bool:
    normalized = _primary_sentence(value).rstrip(".!?。！？").rstrip()
    if not normalized:
        return False
    # These are proposition types, so they outrank incidental event words inside
    # subordinate/background phrases such as `계약 체결 후 ... 충족해야 한다`.
    if _PRIMARY_GOAL_RE.search(normalized) is not None:
        return True
    if normalized.endswith(_PRIMARY_NORMATIVE_ENDINGS):
        return True
    if any(cue in normalized for cue in _PRIMARY_ANALYTICAL_CUES):
        return True
    if normalized.endswith(_PRIMARY_RESPONSE_ENDINGS) and any(
        cue in normalized for cue in _PRIMARY_ABSTRACT_RESPONSE_CUES
    ):
        return True
    if _has_primary_current_event(normalized):
        return False
    return False


def _current_week_aggregate(value: str) -> bool:
    normalized = " ".join(value.split())
    if not re.search(r"지난\s*주(?:\([^)]{1,40}\))?", normalized):
        return False
    return any(cue in normalized for cue in _CURRENT_WEEK_AGGREGATE_CUES)


def _prior_period_policy_event(value: str) -> bool:
    # Decimal points are numeric punctuation, not sentence boundaries. Removing
    # only digit-to-digit dots lets the detector see `2.50% -> 2.75%` without
    # allowing a match to cross an actual sentence stop.
    normalized = " ".join(value.split())
    decimal_normalized = re.sub(r"(?<=\d)\.(?=\d)", "", normalized)
    return _PRIOR_PERIOD_POLICY_EVENT_RE.search(decimal_normalized) is not None


def stale_explicit_past_event_text(value: str, *, now: datetime | None = None) -> bool:
    return _core_stale_explicit_past_event_text(_primary_sentence(value), now=now)


def stale_relative_past_event_text(value: str) -> bool:
    return _core_stale_relative_past_event_text(_primary_sentence(value))


def stale_relative_period_event_text(value: str) -> bool:
    normalized = _primary_sentence(value)
    # `지난 주말` is one relative-weekend expression. The core pattern's `지난 주`
    # prefix must not reinterpret it as a completed stale week.
    if "지난 주말" in normalized or "지난주말" in normalized:
        return False
    # A fresh article may report a newly computed aggregate over the immediately
    # preceding week. The measurement/report is current even though its window is
    # named `지난주`.
    if _current_week_aggregate(normalized):
        return False
    # Conversely, a prior-period policy action is stale background when the
    # primary visible proposition itself is the old action. Include transitive
    # `올렸다` / `내렸다`, which the original market-price cue set omitted.
    if _prior_period_policy_event(normalized):
        return True
    return _core_stale_relative_period_event_text(normalized)


def stale_day_only_context(value: str, *, now: datetime | None = None) -> bool:
    return _core_stale_day_only_context(_primary_sentence(value), now=now)


def stale_quarter_context(value: str, *, now: datetime | None = None) -> bool:
    return _core_stale_quarter_context(_primary_sentence(value), now=now)


def non_event_analytical_text(value: str) -> bool:
    # Preserve the established whole-card non-event detector because a secondary
    # proposition can still be card-central when the headline explicitly promotes
    # it (e.g. statement + unquantified trend). Add the primary-state detector on
    # top; do not replace the established signal with first-sentence-only logic.
    return _core_non_event_analytical_text(value) or _primary_non_event_state(value)


def publisher_notice_boilerplate(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        any(cue in normalized for cue in _PUBLISHER_NOTICE_PERMISSION_CUES)
        and sum(term in normalized for term in _PUBLISHER_NOTICE_RESTRICTION_TERMS) >= 2
        and any(cue in normalized for cue in _PUBLISHER_NOTICE_LEGAL_CUES)
    )


def standalone_sports_photo_caption(value: str) -> bool:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 180:
        return False
    if sum(normalized.count(mark) for mark in ".!?。！？") > 1:
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if not any(cue in normalized for cue in _SPORTS_DEPICTIVE_ACTION_CUES):
        return False
    return normalized.endswith(_SPORTS_DEPICTIVE_ENDINGS)
