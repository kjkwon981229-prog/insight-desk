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
from .sentences import split_sentences
from .text import normalize

MAX_REASON_CHARS = 100
# 예전 고정 문구가 화면에 새지 않도록 막는 문자열(포함되면 거부).
LEAKED_TEMPLATE_PHRASES = ("같은 구체적 수치", "구체적 수치")
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
    # 고정 문장에 수치만 끼우면 기사마다 같은 문구가 되므로, 수치·기록이 든 본문 문장을 그대로 보여 준다.
    figure = _first_figure(title) or _first_figure(body[:800])
    record = _first_word(_RECORD_WORDS, text)
    for needle in (figure, record):
        if needle is None:
            continue
        sentence = _sentence_with(needle, title, body)
        if sentence is not None:
            return f"새로 남는 것: {sentence}"
    if figure is not None:
        return f"새로 남는 것: {figure} 수치가 나옴"
    if record is not None:
        return f"새로 남는 것: '{record}' 기록 언급"
    if _first_word(_ANGLE_WORDS, text) is not None:
        return "새로 남는 것: 배경·분석을 다룸"
    return "새로 남는 것: 새 소식을 담음"


def _sentence_with(needle: str, title: str, body: str) -> str | None:
    """needle이 든 본문 문장 중 제목과 겹치지 않고 짧게 읽히는 것을 고른다."""
    folded_title = normalize(title)
    for sentence in split_sentences(body):
        if needle not in sentence:
            continue
        cleaned = sentence.strip().rstrip(".。")
        if not 12 <= len(cleaned) <= 70:
            continue
        if normalize(cleaned) in folded_title or folded_title in normalize(cleaned):
            continue
        return cleaned
    return None


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
    if any(phrase in reason for phrase in LEAKED_TEMPLATE_PHRASES):
        return False
    full = f"{title} {body}"
    checked = re.sub(r"\([^)]*\)", "", reason)
    for quoted in re.findall(r"'([^']+)'", checked):
        if quoted not in full:
            return False
    present = {number.replace(",", "") for number in _NUMBER.findall(full)}
    return all(number.replace(",", "") in present for number in _NUMBER.findall(checked))
