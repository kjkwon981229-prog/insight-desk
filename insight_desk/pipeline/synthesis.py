from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from ..domain.models import Certainty, EvidenceType, StoryFacts, TrendMetric
from .clustering import StoryCluster
from .editorial import effective_lead, effective_title, safe_evidence_text
from .normalization import normalize_text

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z가-힣])\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|원|%|퍼센트|명|건|배|개|곳|일|년|개월|분|시|위|점|대|km))?"
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
    "발매",
    "발표",
    "공개",
    "시행",
    "선발",
    "경기",
    "매각",
    "인수",
    "인상",
    "인하",
    "규제",
    "유치",
    "투자",
    "인수",
    "트레이드",
    "부상",
    "승리",
    "패배",
    "컴백",
    "전략",
    "할당",
    "계약",
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
_EVENT_ACTIONS = {"시구", "개최", "공연", "콘서트", "선발", "경기", "컴백"}
_SUBJECT_END_MARKERS = ("회동", "시구", "경기", "공연", "콘서트", "출시", "공지")
_DIRECTIONAL_CHANGE_WORDS = {"증가", "감소", "상승", "하락", "확대", "축소", "돌파", "급등", "급락"}
_TRUNCATION_RE = re.compile(r"\.{2,}|…")
_TIME_PREFIX_RE = re.compile(r"^(?:한|두|세|몇|\d+)\s?(?:달|주|일|시간)\s?만에\b")
_DATE_COUNTER_RE = re.compile(r"^(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일))$")
_MARKET_RUN_RE = re.compile(r"\d+\s?거래일(?:\s?연속)?\s?(?:순매수|순매도)")


def _clean_headline(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"^\s*(?:\[[^]]+\]|속보|단독|전문)\s*[:：]?\s*", "", text)
    text = text.replace("원달러", "원·달러")
    # A search title containing an ellipsis may be truncated. Keep the
    # complete clause before the marker; never expose the marker or its
    # possibly incomplete tail as briefing copy.
    marker = _TRUNCATION_RE.search(text)
    if marker:
        text = text[: marker.start()]
    text = re.sub(r"[\"'“”‘’]", "", text)
    text = re.sub(r"\s*[?!]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .·-—")
    text = re.sub(r"^[^0-9A-Za-z가-힣]+", "", text)
    return text


def _editorial_headline(value: str, *, subject: str = "") -> str:
    """Reduce a source headline to a complete, non-truncated display phrase."""

    raw = normalize_text(value)
    cleaned = _clean_headline(raw)
    if _TRUNCATION_RE.search(raw):
        clauses = [part.strip(" ,·-—") for part in re.split(r"[,，|｜:：]", cleaned) if part.strip()]
        first = clauses[0] if clauses else ""
        if len(first) >= 5:
            return first
        if subject.strip():
            return f"{subject.strip()} 관련 보도"
    if len(cleaned) <= 56:
        return cleaned
    clauses = [part.strip(" ,·-—") for part in re.split(r"[,，|｜:：]", cleaned) if part.strip()]
    for clause in clauses:
        if 8 <= len(clause) <= 56:
            return clause
    return cleaned


def _best_title_item(items: tuple[object, ...]) -> object:
    """Choose the most informative headline inside a corroborated cluster."""

    def quality(item: object) -> tuple[float, float, str]:
        title = effective_title(item)
        compact = re.sub(r"\s+", "", title)
        score = min(48.0, len(compact))
        if item.metadata_title and safe_evidence_text(item.metadata_title):
            score += 18.0
        if any(marker in title for marker in (*_ACTION_MARKERS, "차트", "수상", "변동폭", "최대", "최고")):
            score += 16.0
        if re.search(r"^(?:내일의|오늘의)\s*(?:경기|일정)", title):
            score -= 20.0
        if title.startswith(("관련 보도", "관련 소식", "관련 기사")):
            score -= 30.0
        if _TRUNCATION_RE.search(getattr(item, "title", "")):
            score -= 12.0
        heat_sports = (
            any(term in title for term in ("폭염", "열파"))
            and any(term in title for term in ("KBO", "프로야구", "야구"))
        )
        if heat_sports:
            # Prefer the concrete league interruption headline over an
            # analysis headline such as ``선발진 리셋`` inside the same event.
            score += 24.0
            if any(term in title for term in ("중단", "멈춘", "취소")):
                score += 12.0
            if any(term in title for term in ("→", "리셋", "체력 충전")):
                score -= 10.0
        return score, float(getattr(item, "score", 0.0)), title

    return max(items, key=quality)


def _safe_evidence_text(value: str) -> str:
    """Return a snippet only when it is a complete, non-truncated fragment."""

    text = normalize_text(value)
    return "" if _TRUNCATION_RE.search(text) else text


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _numbers(text: str) -> tuple[str, ...]:
    values = []
    for match in _NUMBER_RE.findall(text):
        value = re.sub(r"\s+", "", match)
        if value not in values:
            values.append(value)
    return tuple(values)


def _meaningful_numbers(values: tuple[str, ...], context: str = "") -> tuple[str, ...]:
    """Discard bare counters accidentally captured from Korean headlines."""

    if any(marker in context.casefold() for marker in ("ndf", "선물환")) and "/" in context:
        return values
    meaningful = tuple(value for value in values if re.search(r"[^\d,.\s]", value))
    if meaningful:
        return meaningful
    if values and all(_DATE_COUNTER_RE.fullmatch(value) for value in values):
        return ()
    return values


def _market_run_phrase(title: str) -> str:
    match = _MARKET_RUN_RE.search(_clean_headline(title))
    return match.group(0) if match else ""


def _market_quote_detail(title: str, numbers: tuple[str, ...], change: str) -> str:
    """Preserve an NDF quote pair and its movement without adding context."""

    cleaned = _clean_headline(title)
    if not any(marker in cleaned.casefold() for marker in ("ndf", "선물환")) or len(numbers) < 2:
        return ""
    direction = next((marker for marker in _DIRECTIONAL_CHANGE_WORDS if marker in cleaned), "")
    if not direction:
        return ""
    values = [re.sub(r"\s+", "", value).removesuffix("원") for value in numbers[:3]]
    if len(values) >= 3:
        return f"{values[0]}/{values[1]}원, {values[2]}원 {direction}"
    return f"{values[0]}/{values[1]}원 {direction}"


def _market_metric_number(title: str, numbers: tuple[str, ...]) -> str:
    """Return a number only when the headline ties it to the metric.

    A level such as ``1300원대 환율`` must not be rendered as the size of a
    later-mentioned ``변동폭``.  If a variability marker is present, only a
    number immediately following that marker is safe to reuse.
    """

    if not numbers:
        return ""
    cleaned = _clean_headline(title)
    marker = re.search(r"변동폭|변동성", cleaned)
    if marker:
        nearby = _NUMBER_RE.search(cleaned[marker.end() : marker.end() + 32])
        return nearby.group(0).replace(" ", "") if nearby else ""
    return numbers[0]


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
    if any(word in text for word in ("1위", "차트", "관왕", "수상")):
        return "AWARD_CHART"
    if any(word in text for word in ("규제", "법안", "고시", "금지", "허용")):
        return "REGULATION"
    if any(word in text for word in ("정책", "시행", "대책", "규정", "기준금리")):
        return "POLICY"
    if any(word in text for word in ("출시", "발매", "선공개", "음원", "예약판매", "판매 개시", "사양 확정")):
        return "PRODUCT_RELEASE"
    sports_context = any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기", "시구"))
    if (
        sports_context
        and any(word in text for word in ("폭염", "열파"))
        and any(word in text for word in ("중단", "멈춘", "휴식", "재개", "취소"))
    ):
        return "SPORTS_INTERRUPTION"
    if any(word in text for word in ("부상", "트레이드", "엔트리", "선발")):
        return "ROSTER_PERSONNEL"
    if sports_context and _DATE_RE.search(text) and any(word in text for word in ("시구", "개최", "예정")):
        return "SPORTS_EVENT"
    if any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기 결과")) and any(word in text for word in ("중단", "멈춘", "폭염")):
        return "SPORTS_INTERRUPTION"
    if any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기 결과")) and any(word in text for word in ("경기 결과", "승리했다", "패배했다", "우승", "승률", "연승", "연패", "홈런", "순위")):
        return "SPORTS_RESULT"
    if any(word in text for word in ("콘서트", "공연", "앨범", "컴백", "배우", "가수", "시구")):
        return "ENTERTAINMENT_EVENT"
    if any(word in text for word in ("환율", "원달러", "원·달러", "코스피", "주가", "증시", "금리")):
        return "MARKET"
    if numbers and any(word in text for word in (*_CHANGE_MARKERS, "평균", "통계", "지표", "비율", "변동폭")):
        return "STATISTIC"
    if any(word in text for word in ("유치", "투자", "인수", "전략", "데이터센터", "할당", "계약", "생산")):
        return "INDUSTRY_CHANGE"
    if _DATE_RE.search(text) and any(word in text for word in (*_ACTION_MARKERS, "예정", "진행", "프로젝트", "선보인다")):
        return "SCHEDULED_EVENT"
    if any(word in text for word in ("공식 발표", "발표", "공지")):
        return "ANNOUNCEMENT"
    if any(word in text for word in ("공식 발표", "발표", "공지", "공개")):
        return "ANNOUNCEMENT"
    if any(word in text for word in ("굿즈", "유니폼", "패션", "상품", "기념품")):
        return "MERCHANDISE"
    return "OTHER"


def _subject(title: str, action: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    first_number = next((cleaned.find(value) for value in numbers if cleaned.find(value) >= 0), -1)
    if first_number > 0:
        candidate = cleaned[:first_number]
    elif action and action in cleaned:
        candidate = cleaned[: cleaned.find(action)]
    else:
        marker = next((value for value in _SUBJECT_END_MARKERS if value in cleaned), "")
        if marker:
            candidate = cleaned[: cleaned.find(marker) + len(marker)]
        else:
            candidate = cleaned.split(" · ", 1)[0]
    if "," in candidate or "，" in candidate:
        candidate = re.split(r"[,，]", candidate, maxsplit=1)[0]
    candidate = re.sub(r"^(?:올해|지난해|이번|내년)\s+", "", candidate).strip(" ,·-")
    candidate = re.sub(r"\s+(?:어디|왜|무슨)\s*(?:갔나|일까|인가)?$", "", candidate).strip(" ,·-")
    candidate = re.sub(r"^\d[\d,.]*\s?원대\s+", "", candidate).strip(" ,·-")
    if len(candidate) < 2:
        candidate = cleaned.split(" · ", 1)[0].strip(" ,·-")
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
        # Description snippets can begin or end in the middle of a sentence.
        # Such fragments are evidence only, never a display fact.
        if _TRUNCATION_RE.search(fragment):
            continue
        if fragment and fragment not in phrases:
            phrases.append(fragment)
    return tuple(phrases[:2])


def _tail_after_first_number(title: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    for number in numbers:
        index = cleaned.find(number)
        if index >= 0:
            tail = cleaned[index + len(number) :].strip(" ,·-")
            for marker in _CHANGE_MARKERS:
                marker_index = tail.find(marker)
                if marker_index < 0:
                    continue
                prefix = tail[:marker_index].strip(" ,·-—")[-16:]
                prefix = re.sub(r"^.*?변동폭\s*", "", prefix)
                value = f"{prefix} {marker}".strip()
                if value and value not in _GENERIC_CHANGE_WORDS:
                    return value
            break
    return ""


def _fact_subject(value: str) -> str:
    """Keep the subject compact when a headline embeds comparison context."""

    text = re.sub(r"\s+", " ", value).strip(" ,·-")
    text = re.split(r"\s+(?:금융위기|코로나|전년|지난해|이후|대비|역대)", text, maxsplit=1)[0]
    text = re.sub(r"\s+(?:최고|최대|최저|최소|급등|급락|상승|하락)$", "", text)
    text = re.sub(r"\s+(?:어디|왜|무슨)\s*(?:갔나|일까|인가)?$", "", text)
    text = re.sub(r"^\d[\d,.]*\s?원대\s+", "", text)
    return text.strip(" ,·-")


def _domain_subject(title: str, subject: str, event_type: str) -> str:
    """Replace a clickbait lead with the stable noun users need."""

    if event_type in {"MARKET", "STATISTIC"}:
        if any(term in title for term in ("환율", "원달러", "원·달러")):
            return "원·달러 환율"
        if "코스피" in title or "KOSPI" in title:
            return "코스피"
        if any(term in title for term in ("증시", "주가", "주식")) and subject in {"이젠", "올해", "이번"}:
            return "증시"
    return subject


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
        run_phrase = _market_run_phrase(cleaned)
        if run_phrase:
            return f"{subject} {run_phrase}"
        metric_number = _market_metric_number(cleaned, numbers)
        if not metric_number:
            return f"{subject} {change}" if change and change not in _GENERIC_CHANGE_WORDS else subject
        result = f"{subject} {metric_number}"
        if change and change not in _GENERIC_CHANGE_WORDS and change not in result:
            result += f" · {change}"
        return result
    if event_type == "SPORTS_INTERRUPTION":
        league = "프로야구" if "프로야구" in cleaned or "프로야구" in subject else ("KBO" if "KBO" in cleaned else subject)
        return f"{league} 폭염으로 경기 중단" if league else "폭염으로 경기 중단"
    if event_type in {"AWARD_CHART", "PRODUCT_RELEASE", "INDUSTRY_CHANGE", "REGULATION", "POLICY", "ANNOUNCEMENT"}:
        return cleaned or subject or "주요 변화"
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        if event_type == "SCHEDULED_EVENT" and any(
            marker in cleaned for marker in ("프로젝트", "기념", "선보인다")
        ) and len(cleaned) <= 60:
            return _editorial_headline(cleaned, subject=subject)
        # Keep event headlines factual and short; omit article-style hype
        # after the event verb.
        event_action = action if action in _EVENT_ACTIONS else ""
        event_date = date if date and date not in subject else ""
        if event_action:
            return " ".join(part for part in (subject, event_date, event_action) if part).strip() or cleaned
        return f"{subject} 일정" if date else subject
    return _editorial_headline(title, subject=subject)


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
        summary_subject = "" if _TIME_PREFIX_RE.match(subject) else subject
        summary_subject = _fact_subject(summary_subject)
        quote_detail = _market_quote_detail(title, numbers, change)
        run_phrase = _market_run_phrase(title)
        if quote_detail:
            source_note = "여러 보도에서 확인됐다." if source_count > 1 else "한 건의 보도에서 제시됐다."
            sentence = f"{summary_subject} {quote_detail}이 {source_note}"
        elif run_phrase:
            sentence = f"{summary_subject}의 {run_phrase}가 이어졌다."
        elif (
            event_type == "MARKET"
            and len(numbers) >= 2
            and any(marker in change for marker in ("최대", "최고", "급등", "급락", "변동"))
        ):
            sentence = f"{summary_subject} 변동폭이 {numbers[0]}과 {numbers[1]} 사이를 오가며 {change} 수준으로 확대됐다."
        elif (
            event_type == "MARKET"
            and change
            and any(marker in change for marker in ("최대", "최고", "변동폭"))
        ):
            metric_number = _market_metric_number(title, numbers)
            if metric_number:
                sentence = f"{summary_subject} 변동폭이 {_number_with_ro(metric_number)} {change} 수준으로 확대됐다."
            else:
                sentence = f"{summary_subject} 변동성이 {change} 수준으로 확대됐다."
        elif change and change not in _GENERIC_CHANGE_WORDS:
            marker = next((word for word in _DIRECTIONAL_CHANGE_WORDS if change.endswith(word)), "")
            if marker and summary_subject and numbers[0].endswith(("%", "달러")):
                sentence = f"{summary_subject}{_particle(summary_subject)} {_number_with_ro(numbers[0])} {marker}했다."
            else:
                lead = f"{summary_subject}의 " if summary_subject else ""
                sentence = f"{lead}{numbers[0]} 수치가 "
                sentence += "여러 보도에서 확인됐다." if source_count > 1 else "한 건의 보도에서 제시됐다. 추가 확인이 필요하다."
        elif source_count > 1:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 여러 보도에서 확인됐다."
        else:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 한 건의 보도에서 제시돼 추가 확인이 필요하다."
    elif event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        event_phrase = action if action in _EVENT_ACTIONS else ""
        if event_type == "ENTERTAINMENT_EVENT" and ("컴백" in title or action == "컴백") and date:
            sentence = f"{subject}가 {date} 컴백한다."
        elif event_type == "ENTERTAINMENT_EVENT" and ("앨범" in title or action == "발매") and date:
            sentence = f"{subject}가 {date} 앨범을 발매한다."
        elif date or location:
            when = f"{date} " if date else ""
            where = f"{location}에서 " if location else ""
            phrase = f"{event_phrase} 일정이" if event_phrase else "일정이"
            sentence = f"{subject} {phrase} {when}{where}예정돼 있다."
        else:
            phrase = f"{event_phrase} 일정이" if event_phrase else "일정이"
            sentence = f"{subject} {phrase} 공개됐다."
    elif event_type in {"POLICY", "REGULATION"} and subject:
        policy_action = action if action in {"발표", "공개", "시행", "고시", "확정"} else "정책 변화"
        sentence = f"{subject}의 {policy_action} 내용이 확인됐다."
    elif event_type == "PRODUCT_RELEASE" and subject:
        release_subject = _clean_headline(title).split(",", 1)[0].strip() or subject
        if "앨범" in title:
            release_fact = "앨범 발매"
        elif "음원" in title or "싱글" in title:
            release_fact = "음원 공개"
        elif "도구" in title or "서비스" in title:
            release_fact = "도구·서비스 출시"
        else:
            release_fact = "출시·발매"
        sentence = f"{release_subject}의 {release_fact} 소식이 확인됐다."
    elif event_type == "AWARD_CHART" and subject:
        chart_number = next((value for value in numbers if value.endswith("위")), "")
        if chart_number:
            sentence = f"{subject}가 음악 차트 {chart_number}에 올랐다."
        else:
            sentence = f"{subject}의 차트·수상 성과가 확인됐다."
    elif event_type == "INDUSTRY_CHANGE" and subject:
        change_action = {
            "유치": "투자 유치",
            "투자": "투자",
            "인수": "인수",
            "전략": "전략 변화",
            "할당": "물량 할당",
            "계약": "계약",
            "생산": "생산",
        }.get(action, action or "사업 변화")
        key_number = next(
            (value for value in numbers if not re.search(r"(?:년|월|일)$", value)),
            "",
        )
        if key_number:
            sentence = f"{subject}의 {key_number} 규모 {change_action} 소식이 보도됐다."
        else:
            sentence = f"{subject}의 {change_action} 소식이 보도됐다."
    elif event_type == "ROSTER_PERSONNEL" and subject:
        sentence = f"{subject}의 {action or '선수단 변동'}이 확인됐다."
    elif event_type == "SPORTS_RESULT" and subject:
        sentence = f"{subject}의 경기 결과 또는 기록 변화가 확인됐다."
    elif event_type == "SPORTS_INTERRUPTION" and subject:
        league = "프로야구" if "프로야구" in title or "프로야구" in subject else ("KBO" if "KBO" in title else subject)
        sentence = f"{league} 경기가 폭염 영향으로 중단돼 일정 조정이 필요해졌다."
    elif event_type == "MERCHANDISE" and subject:
        sentence = f"{subject} 관련 상품 소식이 보도됐다."
    elif event_type == "ANNOUNCEMENT":
        if "콘셉트 포토" in title and subject:
            sentence = f"{subject}가 데뷔 콘셉트 포토를 공개했다."
        elif action == "공개" and subject:
            sentence = f"{subject}의 공개 내용이 확인됐다."
        else:
            sentence = f"{subject or _clean_headline(title)} 발표가 확인됐다."
    else:
        if source_count > 1:
            sentence = "여러 매체가 같은 이슈를 전했지만, 공통으로 확인되는 세부 사실은 제한적이다."
        else:
            sentence = "단일 검색 결과만 확인되어 세부 내용은 추가 확인이 필요하다."
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
        f"{effective_title(item)} {effective_lead(item)}" for item in items
    )
    headline_item = _best_title_item(items)
    title = effective_title(headline_item) or _clean_headline(headline_item.title)
    numbers = _unique(list(_numbers(combined)))
    display_numbers = _meaningful_numbers(numbers, title)
    dates = _unique(list(_dates(combined)))
    times = _unique(list(_times(combined)))
    locations = _locations(combined)
    # Classify the representative headline first. Descriptions may mention
    # generic words such as "정책" or "공개" while the headline carries the
    # actual subject (for example a market statistic). This keeps the
    # synthesis anchored to the strongest visible evidence.
    title_event_type = _event_type(title, _numbers(title))
    lead_event_type = _event_type(effective_lead(headline_item), _numbers(effective_lead(headline_item)))
    event_type = title_event_type if title_event_type != "OTHER" else (
        lead_event_type if lead_event_type != "OTHER" else _event_type(combined, numbers)
    )
    action = _action(title) or _action(effective_lead(headline_item)) or _action(combined)
    subject = _domain_subject(title, _subject(title, action, display_numbers), event_type)
    change = _tail_after_first_number(title, display_numbers) or (_change_phrases(title)[:1] or ("",))[0]
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
        key_numbers=display_numbers[:3],
        key_changes=_unique(
            ([change] if change else [])
            + list(_change_phrases(" ".join(_clean_headline(getattr(item, "title", "")) for item in items)))
        )[:2],
        official_source=official,
        source_count=source_count,
        source_diversity=source_count,
        repeated_facts=repeated[:3],
        unique_facts=unique_facts[:3],
        trend_state=trend_state,
        next_known_event=next_signal,
        uncertainty=uncertainty,
    )
    headline_source = effective_title(headline_item)
    if not headline_item.metadata_title or not safe_evidence_text(headline_item.metadata_title):
        headline_source = headline_item.title
    headline = _headline(headline_source, event_type, subject, display_numbers, change, date=date, action=action)
    summary = _summary(
        title,
        event_type,
        subject,
        action,
        date,
        location,
        display_numbers,
        change,
        source_count,
        uncertainty,
    )
    evidence = _evidence_summary(source_count, repeated, official)
    watch = (next_signal,) if next_signal else ()
    if source_count > 1 or official:
        certainty = Certainty.CONFIRMED
    elif event_type != "OTHER" and (numbers or dates or action):
        certainty = Certainty.SUPPORTED_SINGLE_SOURCE
    else:
        certainty = Certainty.UNCERTAIN
    return headline, summary, evidence, watch, facts, certainty
