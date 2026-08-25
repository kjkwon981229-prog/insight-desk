from __future__ import annotations

import re

# Low-level story-quality detectors live here. They expose individual signals only;
# admission policy composition belongs exclusively to story_admission.py.
from insight_desk.feed_quality_detectors_core import *  # noqa: F401,F403
from insight_desk.feed_quality_detectors_core import (
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


def stale_relative_period_event_text(value: str) -> bool:
    normalized = " ".join(value.split())
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
    # visible proposition itself is the old action. Include transitive `올렸다` /
    # `내렸다`, which the original intransitive market-price cue set omitted.
    if _prior_period_policy_event(normalized):
        return True
    return _core_stale_relative_period_event_text(normalized)


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
