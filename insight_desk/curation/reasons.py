from __future__ import annotations

import re
from datetime import datetime

from .scoring import (
    _ANGLE_WORDS,
    _DATE_PATTERN,
    _RECORD_WORDS,
    _TIME_EXPRS,
    _has_date_in_range,
    ScoreResult,
)
from .text import normalize

MAX_REASON_CHARS = 100
_DATE_UNITS = ("년", "월", "일")
_NUMBER_WITH_UNIT = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s?(?:억원|만원|조원|천원|%|원|억|만|명|건|개|위|승|패|점|회|배|달러|홈런|타점|이닝)"
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _first_figure(text: str) -> str | None:
    for match in _NUMBER_WITH_UNIT.finditer(text):
        figure = match.group(0).strip()
        if figure.endswith(_DATE_UNITS):
            continue
        return figure
    return None


def _first_word(words: tuple[str, ...], text: str) -> str | None:
    folded = normalize(text)
    for word in words:
        if normalize(word) in folded:
            return word
    return None


def _reason_q1(text: str, title: str = "", body: str = "") -> str:
    # 엉뚱한 곳의 숫자를 고르지 않도록 제목, 그다음 본문 앞부분에서만 수치를 찾는다.
    figure = _first_figure(title) or _first_figure(body[:800])
    if figure is not None:
        return f"새로 남는 것: {figure} 같은 구체적 수치"
    record = _first_word(_RECORD_WORDS, text)
    if record is not None:
        return f"새로 남는 것: '{record}' 기록 언급"
    if _first_word(_ANGLE_WORDS, text) is not None:
        return "새로 남는 것: 배경·분석을 다룸"
    return "새로 남는 것: 새 소식을 담음"


def _reason_q3(text: str, now: datetime) -> str:
    for match in _DATE_PATTERN.finditer(text):
        if _has_date_in_range(match.group(0), now):
            return f"{match.group(1)}월 {match.group(2)}일 일정이 있어 바로 확인할 수 있음"
    word = _first_word(_TIME_EXPRS, text)
    if word is not None:
        return f"'{word}' 기준 소식이라 바로 쓸 수 있음"
    return "오늘·이번 주 바로 쓸 수 있는 정보"


def build_reason(
    *,
    score: ScoreResult,
    topic_label: str,
    title: str,
    body: str,
    now: datetime,
) -> str:
    """고른 이유 한 줄. 문장 틀은 고정이고 숫자·낱말은 본문에서만 가져온다(외부 모델 없음)."""
    text = f"{title} {body}"
    if score.top_question == "q2":
        reason = f"관심 분야({topic_label})와 직접 관련"
    elif score.top_question == "q3":
        reason = _reason_q3(text, now)
    else:
        reason = _reason_q1(text, title, body)
    return reason[:MAX_REASON_CHARS]


def reason_is_grounded(reason: str, body: str, title: str = "") -> bool:
    """이유 속 따옴표 낱말과 숫자가 모두 제목+본문에 그대로 있는지 확인한다."""
    full = f"{title} {body}"
    checked = re.sub(r"\([^)]*\)", "", reason)
    for quoted in re.findall(r"'([^']+)'", checked):
        if quoted not in full:
            return False
    present = {number.replace(",", "") for number in _NUMBER.findall(full)}
    return all(number.replace(",", "") in present for number in _NUMBER.findall(checked))
