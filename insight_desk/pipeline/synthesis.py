from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from ..domain.models import Certainty, EvidenceType, StoryFacts, TrendMetric
from .clustering import StoryCluster
from .normalization import normalize_text

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z가-힣])\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|달러|원|%|퍼센트|명|건|배|개|곳|일|년|개월|분|시|위|점|대|km))?"
)
_DATE_RE = re.compile(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)")
_TIME_RE = re.compile(r"(?:오전|오후)\s?\d{1,2}(?::\d{2})?|\d{1,2}\s?시(?:\s?\d{1,2}\s?분)?")
_CHANGE_MARKERS = (
    "최고",
    "최대",
    "최저",
    "최소",
    "증가",
    "감소",
    "상승",
    "하락",
    "확대",
    "축소",
    "돌파",
    "기록",
    "사상",
    "역대",
    "급등",
    "급락",
)
_ACTION_MARKERS = (
    "시구",
    "개최",
    "공연",
    "콘서트",
    "출시",
    "발표",
    "공개",
    "시행",
    "선발",
    "경기",
    "매각",
    "인수",
    "인상",
    "인하",
)
_LOCATION_TERMS = (
    "잠실",
    "서울",
    "부산",
    "광주",
    "대전",
    "인천",
    "제주",
    "판교",
    "여의도",
    "뉴욕",
    "도쿄",
    "싱가포르",
    "충칭",
    "DDP",
)
_STOPWORDS = {
    "관련",
    "보도",
    "추가",
    "내용",
    "결과",
    "발표",
    "공개",
    "확인",
    "전해져",
    "전해졌다",
    "밝혀져",
    "올해",
    "지난해",
    "이번",
    "내년",
    "따르면",
    "대해",
    "위해",
    "에서",
    "으로",
    "있는",
    "있다",
    "같은",
    "및",
    "또",
}
_GENERIC_CHANGE_WORDS = {"기록", "발표", "공개", "확인"}


def _clean_headline(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"^\s*(?:\[[^]]+\]|속보|단독|전문)\s*[:：]?\s*", "", text)
    text = text.replace("원달러", "원·달러")
    # Search headlines often use one ellipsis as a visual separator. It is
    # still an indication that the source title was copied, so remove it
    # before the title becomes user-facing briefing copy.
    text = re.sub(r"(?:\.{2,}|…)", " ", text)
    text = re.sub(r"[\"“”‘’]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .·-—")
    return text


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _numbers(text: str) -> tuple[str, ...]:
    values = []
    for match in _NUMBER_RE.findall(text):
        value = re.sub(r"\s+", "", match)
        if value not in values:
            values.append(value)
    return tuple(values)


def _dates(text: str) -> tuple[str, ...]:
    return _unique([re.sub(r"\s+", "", value) for value in _DATE_RE.findall(text)])


def _times(text: str) -> tuple[str, ...]:
    return _unique([re.sub(r"\s+", "", value) for value in _TIME_RE.findall(text)])


def _locations(text: str) -> tuple[str, ...]:
    return _unique([value for value in _LOCATION_TERMS if value.casefold() in text.casefold()])


def _repeated_values(
    items: tuple[object, ...], extractor: Callable[[str], tuple[str, ...]]
) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for item in items:
        values = extractor(f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}")
        counts.update(set(values))
    return tuple(value for value, count in counts.most_common() if count >= 2)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9가-힣·]{2,}", text)
        if token not in _STOPWORDS and not token.isdigit()
    }


def _repeated_terms(items: tuple[object, ...]) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(_tokens(_clean_headline(getattr(item, "title", ""))))
    return tuple(token for token, count in counts.most_common() if count >= 2)[:3]


def _event_type(text: str, numbers: tuple[str, ...]) -> str:
    if any(word in text for word in ("실적", "매출", "영업이익", "순이익", "가이던스")):
        return "EARNINGS"
    if any(word in text for word in ("정책", "시행", "고시", "법안", "대책", "규정", "기준금리")):
        return "POLICY"
    if any(word in text for word in ("출시", "예약판매", "판매 개시", "사양 확정")):
        return "PRODUCT_RELEASE"
    if any(word in text for word in ("경기", "시구", "선발", "엔트리", "승리", "패배", "홈런")):
        return "SPORTS_EVENT"
    if any(word in text for word in ("콘서트", "공연", "앨범", "컴백", "배우", "가수", "시구")):
        return "ENTERTAINMENT_EVENT"
    if any(word in text for word in ("환율", "코스피", "주가", "증시", "금리")):
        return "MARKET"
    if numbers and any(word in text for word in (*_CHANGE_MARKERS, "평균", "통계", "지표", "비율", "변동폭")):
        return "STATISTIC"
    if _DATE_RE.search(text) and any(word in text for word in (*_ACTION_MARKERS, "예정")):
        return "SCHEDULED_EVENT"
    if any(word in text for word in ("공식 발표", "발표", "공개", "확정")):
        return "ANNOUNCEMENT"
    return "OTHER"


def _subject(title: str, action: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    first_number = next((cleaned.find(value) for value in numbers if cleaned.find(value) >= 0), -1)
    if first_number > 0:
        candidate = cleaned[:first_number]
    elif action and action in cleaned:
        candidate = cleaned[: cleaned.find(action)]
    else:
        candidate = cleaned.split(" · ", 1)[0]
    candidate = re.sub(r"^(?:올해|지난해|이번|내년)\s+", "", candidate).strip(" ,·-")
    return candidate[:48]


def _action(text: str) -> str:
    return next((word for word in _ACTION_MARKERS if word in text), "")


def _change_phrases(text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for marker in _CHANGE_MARKERS:
        index = text.find(marker)
        if index < 0:
            continue
        start = max(0, index - 14)
        end = min(len(text), index + len(marker) + 8)
        fragment = re.sub(r"\s+", " ", text[start:end]).strip(" ,·")
        if fragment and fragment not in phrases:
            phrases.append(fragment)
    return tuple(phrases[:2])


def _tail_after_first_number(title: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    for number in numbers:
        index = cleaned.find(number)
        if index >= 0:
            tail = cleaned[index + len(number) :].strip(" ,·-")
            if 2 <= len(tail) <= 28:
                return tail
            break
    return ""


def _trend_state(topic_id: str, metrics: tuple[TrendMetric, ...]) -> str:
    relevant = [metric for metric in metrics if metric.topic_id == topic_id]
    if not relevant:
        return "비교 부족"
    rising = any(metric.delta is not None and metric.delta > 0 for metric in relevant)
    falling = any(metric.delta is not None and metric.delta < 0 for metric in relevant)
    if rising and falling:
        return "혼조"
    if rising:
        return "상승"
    if falling:
        return "둔화"
    if any(metric.interpretation == "비교 기준 부족" for metric in relevant):
        return "비교 부족"
    return "큰 변화 없음"


def _official_source(items: tuple[object, ...]) -> str:
    for item in items:
        if EvidenceType.OFFICIAL_SOURCE in getattr(item, "provenance", ()):
            return "공식 자료"
        domain = str(getattr(item, "source_domain", "")).lower()
        if domain.endswith(".go.kr") or domain.endswith(".gov") or "bok.or.kr" in domain:
            return "공식 자료"
    return ""


def _particle(value: str) -> str:
    if not value:
        return "는"
    last = value[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        return "은" if code % 28 else "는"
    return "는"


def _number_with_ro(value: str) -> str:
    """Attach the Korean instrumental marker without producing ``원로``."""

    return f"{value}로" if value.endswith(("%", "달러")) else f"{value}으로"


def _next_signal(event_type: str, text: str, date: str, action: str) -> str:
    if event_type in {"STATISTIC", "MARKET"}:
        if "월" in text:
            return "다음 월간 통계와 변동폭"
        if "분기" in text:
            return "다음 분기 통계와 변화폭"
        if "연간" in text or "연도" in text:
            return "다음 연간 통계와 변화폭"
        return ""
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and date:
        noun = "경기·행사" if event_type == "SPORTS_EVENT" else "행사"
        return f"{date} {noun} 결과와 공식 후속 발표"
    if event_type == "EARNINGS":
        return "다음 실적 발표와 공시 수치"
    if event_type == "POLICY" and (date or "시행" in text):
        return "시행일과 세부 고시"
    if event_type == "PRODUCT_RELEASE":
        return "공식 출시일과 확정 사양"
    if event_type == "ANNOUNCEMENT" and (
        date or any(word in text for word in ("시행", "실행", "적용", "예정", "출시"))
    ):
        return "실행 시점과 공식 전문"
    return ""


def _headline(
    title: str,
    event_type: str,
    subject: str,
    numbers: tuple[str, ...],
    change: str,
    *,
    date: str = "",
    action: str = "",
) -> str:
    cleaned = _clean_headline(title)
    if event_type in {"STATISTIC", "MARKET", "EARNINGS"} and subject and numbers:
        result = f"{subject} {numbers[0]}"
        if change and change not in _GENERIC_CHANGE_WORDS and change not in result:
            result += f" · {change}"
        return result
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        # Keep event headlines factual and short; omit article-style hype
        # after the event verb.
        event_action = action if action in {"시구", "개최", "공연", "콘서트", "선발", "경기"} else ""
        event_date = date if date and date not in subject else ""
        return " ".join(part for part in (subject, event_date, event_action) if part).strip() or cleaned
    return cleaned


def _summary(
    title: str,
    event_type: str,
    subject: str,
    action: str,
    date: str,
    location: str,
    numbers: tuple[str, ...],
    change: str,
    source_count: int,
    uncertainty: str,
) -> str:
    if event_type in {"STATISTIC", "MARKET", "EARNINGS"} and subject and numbers:
        particle = _particle(subject)
        if change in _GENERIC_CHANGE_WORDS:
            ending = "기록됐다."
        else:
            ending = f"{change} 수준으로 확인됐다." if change else "관련 수치가 확인됐다."
        sentence = f"{subject}{particle} {_number_with_ro(numbers[0])} {ending}"
    elif event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        event_phrase = action if action in {"시구", "개최", "공연", "콘서트", "선발", "경기"} else "행사"
        if date or location:
            when = f"{date} " if date else ""
            where = f"{location}에서 " if location else ""
            sentence = f"{subject} {event_phrase} 일정이 {when}{where}예정돼 있다."
        else:
            sentence = f"{subject} {event_phrase} 일정이 공개됐다."
    elif event_type == "POLICY" and subject:
        sentence = f"{subject} 관련 정책 변화가 발표됐다."
    elif event_type == "PRODUCT_RELEASE" and subject:
        sentence = f"{subject} 출시 또는 판매 일정이 공개됐다."
    elif event_type == "ANNOUNCEMENT":
        sentence = f"{subject or _clean_headline(title)} 발표가 확인됐다."
    else:
        sentence = f"{_clean_headline(title)} 관련 내용이 확인됐다."
    if uncertainty:
        sentence += f" {uncertainty}"
    return sentence.replace("...", "").replace("…", "").strip()


def clean_headline(value: str) -> str:
    """Return a safe display title without search-result formatting artifacts."""

    return _clean_headline(value)


def _evidence_summary(source_count: int, repeated: tuple[str, ...], official: str) -> str:
    if official:
        return "공식 자료를 인용한 보도가 확인됐다."
    if source_count > 1:
        return "여러 매체에서 같은 핵심 내용이 확인됐다."
    return "검색 결과 한 건에서 확인된 내용이다."


def synthesize_cluster(
    cluster: StoryCluster,
    *,
    topic_name: str,
    trend_metrics: tuple[TrendMetric, ...],
) -> tuple[str, str, str, tuple[str, ...], StoryFacts, Certainty]:
    items = cluster.items
    representative = cluster.representative
    combined = " ".join(
        f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}" for item in items
    )
    title = _clean_headline(representative.title)
    numbers = _unique(list(_numbers(combined)))
    dates = _unique(list(_dates(combined)))
    times = _unique(list(_times(combined)))
    locations = _locations(combined)
    # Classify the representative headline first. Descriptions may mention
    # generic words such as "정책" or "공개" while the headline carries the
    # actual subject (for example a market statistic). This keeps the
    # synthesis anchored to the strongest visible evidence.
    title_event_type = _event_type(title, _numbers(title))
    event_type = title_event_type if title_event_type != "OTHER" else _event_type(combined, numbers)
    action = _action(combined)
    subject = _subject(title, action, numbers)
    change = _tail_after_first_number(title, numbers) or (_change_phrases(title)[:1] or ("",))[0]
    repeated = _repeated_values(items, _numbers)
    if not repeated:
        repeated = _repeated_values(items, _dates)
    if not repeated:
        repeated = _repeated_values(items, _locations)
    if not repeated and len(items) > 1:
        repeated = _repeated_terms(items)
    representative_values = _unique(list(_numbers(title)) + list(_dates(title)) + list(_locations(title)))
    unique_facts = tuple(value for value in representative_values if value not in repeated)
    uncertainty = ""
    numeric_values = _repeated_values(items, _numbers)
    all_numeric = _unique(list(_numbers(combined)))
    if len(numeric_values) == 0 and len(all_numeric) > 1 and event_type in {"STATISTIC", "MARKET", "EARNINGS"}:
        units = {re.sub(r"[\d,.\s]", "", value) for value in all_numeric}
        if len(units) == 1:
            uncertainty = "보도마다 수치가 달라 추가 확인이 필요하다."
    official = _official_source(items)
    source_count = cluster.source_count
    trend_state = _trend_state(cluster.topic_id, trend_metrics)
    date = dates[0] if dates else ""
    location = locations[0] if locations else ""
    next_signal = _next_signal(event_type, combined, date, action)
    facts = StoryFacts(
        subject=subject,
        action=action,
        object="",
        event_type=event_type,
        date=date,
        time=times[0] if times else "",
        location=location,
        key_numbers=numbers[:3],
        key_changes=_unique(([change] if change else []) + list(_change_phrases(combined)))[:2],
        official_source=official,
        source_count=source_count,
        source_diversity=source_count,
        repeated_facts=repeated[:3],
        unique_facts=unique_facts[:3],
        trend_state=trend_state,
        next_known_event=next_signal,
        uncertainty=uncertainty,
    )
    headline = _headline(title, event_type, subject, numbers, change, date=date, action=action)
    summary = _summary(
        title,
        event_type,
        subject,
        action,
        date,
        location,
        numbers,
        change,
        source_count,
        uncertainty,
    )
    evidence = _evidence_summary(source_count, repeated, official)
    watch = (next_signal,) if next_signal else ()
    certainty = Certainty.CONFIRMED if source_count > 1 or official else Certainty.UNCERTAIN
    return headline, summary, evidence, watch, facts, certainty
