from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

CONTEST_TOPIC_ID = "contest_benefits"
MIN_DAYS_LEFT = 7

_DATE_FULL = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?")
_DATE_MD_KO = re.compile(r"(?<![\d.])(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DATE_MD_DOT = re.compile(r"(?<![\d.])(\d{1,2})\s*[./]\s*(\d{1,2})(?![\d./])")
_DEADLINE_MARKERS = ("마감", "까지", "접수", "모집", "응모", "제출", "~", "∼", "–")

_NOT_DEADLINE_LEAD = ("시상", "발표", "결과", "수상", "전시", "개최", "행사", "오리엔테이션")
_ELIGIBLE = ("대학생", "대학(원)생", "대학원생", "재학생", "누구나", "제한 없음", "제한없음", "전 국민", "전국민", "청년")
_INELIGIBLE = ("직장인", "재직자", "기업 대상", "법인", "초등학생", "중학생", "고등학생", "청소년 대상", "청소년만", "만 19세 이상 성인")
_COST = ("참가비", "참가 비용", "신청비", "수강료", "유료", "결제", "신용카드", "카드 등록", "카드번호", "구독료", "입금")
_FREE = ("참가비 무료", "참가비 없음", "참가비는 없", "무료")
_INTEREST = ("디자인", "영상", "UCC", "숏폼", "포스터", "일러스트", "웹툰", "글쓰기", "수필", "에세이", "소설", "시나리오", "공모", "AI", "인공지능", "야구", "사진")
_INTEREST_STRICT = ("디자인", "영상", "UCC", "숏폼", "포스터", "일러스트", "웹툰", "글쓰기", "수필", "에세이", "소설", "시나리오", "AI", "인공지능", "야구", "사진", "문학", "글")


@dataclass(frozen=True, slots=True)
class ContestVerdict:
    ok: bool
    reason: str | None  # one of CONTEST_REASONS or "contest_not_related"
    deadline: date | None = None
    days_left: int | None = None


def _to_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _candidate_dates(text: str, today: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []
    for match in _DATE_FULL.finditer(text):
        parsed = _to_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if parsed:
            found.append((match.start(), parsed))
            taken.append((match.start(), match.end()))
    for pattern in (_DATE_MD_KO, _DATE_MD_DOT):
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in taken):
                continue
            parsed = _to_date(today.year, int(match.group(1)), int(match.group(2)))
            if parsed is None:
                continue
            if parsed < today - timedelta(days=180):  # 연말에 쓴 다음 해 마감
                parsed = _to_date(today.year + 1, parsed.month, parsed.day) or parsed
            found.append((match.start(), parsed))
            taken.append((match.start(), match.end()))
    return sorted(found)


def extract_deadline(text: str, today: date) -> date | None:
    """마감 표지(마감·까지·접수·~) 근처 날짜 가운데 가장 늦은 날을 마감으로 본다. 표지가 없으면 None."""
    candidates = _candidate_dates(text, today)
    best: date | None = None
    for position, parsed in candidates:
        if any(word in text[max(0, position - 8) : position] for word in _NOT_DEADLINE_LEAD):
            continue  # 시상식·결과 발표일 같은 마감이 아닌 날짜
        window = text[max(0, position - 40) : position + 40]
        if any(marker in window for marker in _DEADLINE_MARKERS):
            if best is None or parsed > best:
                best = parsed
    return best


def verify_contest(*, title: str, body: str, now: datetime) -> ContestVerdict:
    """공모전·혜택 글의 원문(가져온 페이지) 글자에서 마감·자격·비용·관심 분야를 확인한다.

    확인하지 못한 항목은 통과시키지 않는다(`contest_unverified`).
    """
    text = f"{title}\n{body}"
    today = now.date()

    deadline = extract_deadline(text, today)
    if deadline is None:
        return ContestVerdict(False, "contest_unverified")
    days_left = (deadline - today).days
    if days_left < 0:
        return ContestVerdict(False, "contest_deadline_passed", deadline, days_left)
    if days_left < MIN_DAYS_LEFT:
        return ContestVerdict(False, "contest_deadline_under_7d", deadline, days_left)

    if any(word in text for word in _COST):
        # "참가비 무료"처럼 무료를 밝힌 문장 안의 비용 낱말은 비용으로 치지 않는다.
        stripped = text
        for phrase in _FREE:
            stripped = stripped.replace(phrase, "")
        if any(word in stripped for word in _COST):
            return ContestVerdict(False, "benefit_costs_money", deadline, days_left)

    has_eligible = any(word in text for word in _ELIGIBLE)
    if not has_eligible:
        if any(word in text for word in _INELIGIBLE):
            return ContestVerdict(False, "contest_ineligible", deadline, days_left)
        return ContestVerdict(False, "contest_unverified", deadline, days_left)

    if not any(word in text for word in _INTEREST_STRICT):
        return ContestVerdict(False, "contest_not_related", deadline, days_left)

    return ContestVerdict(True, None, deadline, days_left)
