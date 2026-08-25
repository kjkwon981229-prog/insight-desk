from __future__ import annotations

import re

# The original detector implementation is byte-preserved in the sibling core.
# This module remains detector-only: it narrows three measured lexical/date
# boundaries and contains no admission composition or topic policy.
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
