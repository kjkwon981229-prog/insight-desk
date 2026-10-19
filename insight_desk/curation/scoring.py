from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .config import CurationConfig
from .text import content_words, normalize

KST = timezone(timedelta(hours=9))

_NUMERIC_UNITS = (
    "%", "원", "억", "만", "명", "건", "개", "위", "승", "패",
    "점", "회", "배", "달러", "$", "홈런", "타점", "이닝",
)

_RECORD_WORDS = (
    "역대", "최초", "사상", "신기록", "처음", "최고", "최저", "최다", "최소",
    "record", "first", "all-time",
)

_ANGLE_WORDS = (
    "배경", "이유는", "원인", "비교", "반면", "분석", "해석", "뒷이야기", "전문가",
    "because", "according to", "versus", "analysis",
)

_TIME_EXPRS = (
    "오늘", "내일", "모레", "이번 주", "이번주", "금주", "today", "tomorrow", "this week",
)

_ACTION_EXPRS = (
    "마감", "접수", "신청", "일정", "발표", "개최", "시행", "공고", "예정",
    "출시", "개막", "경기", "방법", "활용", "적용", "가이드",
    "deadline", "schedule", "announce",
)

_DATE_PATTERN = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_COMING_PATTERN = re.compile(r"오는\s*\d{1,2}\s*일")
_NUM_UNIT_PATTERN = re.compile(r"\d[\d,.]*\s*(?:%|원|억|만|명|건|개|위|승|패|점|회|배|달러|\$|홈런|타점|이닝)")
_DOLLAR_PATTERN = re.compile(r"\$\s*\d[\d,.]*")


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _count_numeric_kinds(text: str) -> int:
    norm = normalize(text)
    kinds: set[str] = set()
    for m in _NUM_UNIT_PATTERN.finditer(norm):
        matched = m.group()
        for unit in _NUMERIC_UNITS:
            if unit == "$":
                continue
            if matched.endswith(unit):
                num_part = matched[: len(matched) - len(unit)].strip().replace(",", "")
                date_like = False
                if unit in ("년", "월", "일"):
                    date_like = True
                if not date_like and num_part:
                    kinds.add(unit)
                break
    for m in _DOLLAR_PATTERN.finditer(norm):
        kinds.add("$")
    return len(kinds)


def _has_record(text: str) -> bool:
    norm = normalize(text)
    return any(w in norm for w in _RECORD_WORDS)


def _has_angle(text: str) -> bool:
    norm = normalize(text)
    return any(w in norm for w in _ANGLE_WORDS)


def _has_time_expr(text: str) -> bool:
    norm = normalize(text)
    if any(e in norm for e in _TIME_EXPRS):
        return True
    if _COMING_PATTERN.search(norm):
        return True
    return False


def _has_action_expr(text: str) -> bool:
    norm = normalize(text)
    return any(e in norm for e in _ACTION_EXPRS)


def _has_date_in_range(text: str, now: datetime) -> bool:
    kst_now = now.astimezone(KST)
    today = kst_now.date()
    end = today + timedelta(days=7)
    for m in _DATE_PATTERN.finditer(text):
        month = int(m.group(1))
        day = int(m.group(2))
        if month < 1 or month > 12 or day < 1 or day > 31:
            continue
        year = today.year
        try:
            import calendar
            max_day = calendar.monthrange(year, month)[1]
            if day > max_day:
                continue
            candidate = datetime(year, month, day, tzinfo=KST).date()
        except ValueError:
            continue
        if candidate < today:
            try:
                candidate = datetime(year + 1, month, day, tzinfo=KST).date()
            except ValueError:
                continue
        if today <= candidate <= end:
            return True
    return False


def _is_recent(published_at: datetime | None, now: datetime) -> bool:
    if published_at is None:
        return False
    return (now - published_at) <= timedelta(hours=24)


def _count_anchor_hits(text: str, anchors: Sequence[str]) -> int:
    norm = normalize(text)
    hits = 0
    for anchor in anchors:
        a = normalize(anchor)
        if not a:
            continue
        if re.search(r"[a-z]", a):
            pattern = r"\b" + re.escape(a) + r"\b"
            if re.search(pattern, norm):
                hits += 1
        else:
            if a in norm:
                hits += 1
    return hits


def _anchor_in_title(title: str, anchors: Sequence[str]) -> bool:
    norm_title = normalize(title)
    for anchor in anchors:
        a = normalize(anchor)
        if not a:
            continue
        if re.search(r"[a-z]", a):
            pattern = r"\b" + re.escape(a) + r"\b"
            if re.search(pattern, norm_title):
                return True
        else:
            if a in norm_title:
                return True
    return False


@dataclass(frozen=True, slots=True)
class ScoreResult:
    q1: int
    q2: int
    q3: int
    base_total: int
    adjust: float
    total: float
    top_question: str
    passed: bool
    reasons: tuple[str, ...]


def score_article(
    *,
    title: str,
    body: str,
    topic_id: str,
    intent_anchors: Sequence[str],
    published_at: datetime | None,
    now: datetime,
    cfg: CurationConfig,
    feedback_adjust: float = 0.0,
) -> ScoreResult:
    combined = title + " " + body
    reasons: list[str] = []

    num_kinds = _count_numeric_kinds(combined)
    has_rec = _has_record(combined)
    has_ang = _has_angle(combined)
    q1 = 0
    if num_kinds >= 3:
        q1 += 2
    elif num_kinds >= 1:
        q1 += 1
    if has_rec:
        q1 += 1
    if has_ang:
        q1 += 1
    q1 = min(q1, 3)
    parts_q1 = []
    if num_kinds:
        parts_q1.append(f"수치 {num_kinds}종")
    if has_rec:
        parts_q1.append("기록")
    if has_ang:
        parts_q1.append("각도")
    if parts_q1:
        reasons.append(f"q1:{'·'.join(parts_q1)}")

    base = cfg.interest_base.get(topic_id, 1)
    hits = _count_anchor_hits(combined, intent_anchors)
    title_hit = _anchor_in_title(title, intent_anchors)
    q2 = base
    if hits >= 4:
        q2 += 1
    if title_hit:
        q2 += 1
    if hits <= 1:
        q2 -= 1
    q2 = max(0, min(3, q2))
    reasons.append(f"q2:앵커 {hits}개·제목 {'일치' if title_hit else '불일치'}")

    q3 = 0
    if _has_time_expr(combined):
        q3 += 1
    if _has_action_expr(combined):
        q3 += 1
    if _has_date_in_range(combined, now) or _is_recent(published_at, now):
        q3 += 1
    q3 = min(q3, 3)
    parts_q3 = []
    if _has_time_expr(combined):
        parts_q3.append("시점")
    if _has_action_expr(combined):
        parts_q3.append("행동")
    if _has_date_in_range(combined, now) or _is_recent(published_at, now):
        parts_q3.append("날짜")
    if parts_q3:
        reasons.append(f"q3:{'·'.join(parts_q3)}")

    base_total = q1 + q2 + q3
    adjust = _clamp(feedback_adjust, cfg.feedback_min, cfg.feedback_max)
    total = base_total + adjust

    scores = [("q1", q1), ("q2", q2), ("q3", q3)]
    scores.sort(key=lambda x: (-x[1], ["q1", "q2", "q3"].index(x[0])))
    top_question = scores[0][0]

    passed = total >= cfg.pass_score_for(topic_id)

    return ScoreResult(
        q1=q1,
        q2=q2,
        q3=q3,
        base_total=base_total,
        adjust=adjust,
        total=total,
        top_question=top_question,
        passed=passed,
        reasons=tuple(reasons),
    )
