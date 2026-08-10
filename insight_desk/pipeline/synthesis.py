from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from ..domain.models import Certainty, EvidenceType, StoryFacts, TrendMetric
from .clustering import StoryCluster
from .editorial import best_headline_item, effective_lead, effective_title, evidence_corroborated, safe_evidence_text
from .normalization import normalize_text
from .semantics import (
    ACTION_TERMS,
    canonical_event_date,
    canonical_event_signature,
    contains_action,
    contains_boundary_term,
    earnings_fact_parts,
    earnings_observations,
    first_action,
    market_direction,
    metric_observations,
    MetricObservation,
    recruitment_event_type,
    summary_information_gain,
    is_trusted_official_domain,
)
from .trend_metrics import effective_trend_state

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z가-힣])\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|개월|주년|분기|원|%|퍼센트|명|건|배|개|곳|일|월|년|분|시|위|점|대|선|km))?"
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
    "강세",
    "약세",
    "강보합세",
)
_ACTION_MARKERS = (
    "요구",
    "촉구",
    "줄여라",
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
    "중단",
    "멈춘",
    "재개",
    "취소",
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
_KBO_TEAM_RE = re.compile(
    r"(?<![A-Za-z가-힣])(?:한화(?:\s*이글스)?|두산(?:\s*베어스)?|LG(?:\s*트윈스)?|"
    r"KT(?:\s*위즈)?|SSG(?:\s*랜더스)?|KIA(?:\s*타이거즈)?|NC(?:\s*다이노스)?|"
    r"롯데(?:\s*자이언츠)?|삼성(?:\s*라이온즈)?|키움(?:\s*히어로즈)?)(?![A-Za-z가-힣])",
    re.IGNORECASE,
)
_LINEUP_LABEL_RE = re.compile(r"^(?:선발(?:투수)?|투수|예고|라인업)\s*", re.IGNORECASE)
_PLAYER_TOKEN_RE = re.compile(r"[A-Za-z가-힣][A-Za-z가-힣·.'’-]{1,11}")
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
_DIRECTIONAL_CHANGE_WORDS = {"증가", "감소", "상승", "하락", "확대", "축소", "돌파", "급등", "급락", "강세", "약세", "강보합세"}
_TRUNCATION_RE = re.compile(r"\.{2,}|…|·{2,}")
_TIME_PREFIX_RE = re.compile(r"^(?:한|두|세|몇|\d+)\s?(?:달|주|일|시간)\s?만에\b")
_DATE_COUNTER_RE = re.compile(r"^(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일|주년))$")
_DATE_STAMP_RE = re.compile(r"^20\d{2}[./-]\d{1,2}[./-]\d{1,2}$")
_TIME_COUNTER_RE = re.compile(r"^\d{1,2}\s?(?:시|분)$")
_MARKET_RUN_RE = re.compile(r"\d+\s?거래일(?:\s?연속)?\s?(?:순매수|순매도)")
_GENERIC_HEADLINE_MARKERS = ("관련 보도", "관련 소식", "관련 기사", "관련 뉴스")
_GENERIC_SUMMARY_MARKERS = (
    "단일 검색 결과만 확인되어",
    "공통으로 확인되는 세부 사실은 제한적이다",
    "소식이 보도됐다",
    "변화가 보도됐다",
    "발표가 확인됐다",
    "공개 내용이 확인됐다",
    "관련 내용이 확인됐다",
    "여러 매체에서 같은 핵심 내용이 확인됐다",
    "여러 보도에서 같은 핵심 내용이 확인됐다",
    "공식 자료를 인용한 보도가 확인됐다",
)
_EVENT_DATE_MARKERS = (
    "발매", "출시", "컴백", "공개", "발표", "개최", "공연", "콘서트", "진행", "시작", "재개",
    "예정", "상장", "시구", "경기", "열렸다", "성료",
)
_COMPLETION_MARKERS = ("대성황", "성황", "성료", "진행했다", "진행됐다", "개최했다", "열렸다", "마쳤다")
def _earnings_fact_parts(text: str) -> tuple[str, str, str]:
    """Keep synthesis on the same fact-bound earnings parser as the event model."""

    return earnings_fact_parts(_clean_headline(text))


def earnings_summary_preserves_fact_binding(headline: str, summary: str) -> bool:
    """Require an earnings display to retain period/metric/value together."""

    period, metric, value = _earnings_fact_parts(headline)
    if not metric or not value:
        return False
    compact_summary = normalize_text(summary).replace(" ", "")
    if metric not in compact_summary or value not in compact_summary:
        return False
    if period and period not in compact_summary:
        return False
    return True


def is_usable_synthesis(
    headline: str,
    summary: str,
    *,
    source_count: int,
    official_source: bool = False,
) -> bool:
    """Reject display copy that cannot carry a concrete editorial fact."""

    clean_headline = normalize_text(headline)
    clean_summary = normalize_text(summary)
    if not clean_headline or any(marker in clean_headline for marker in _GENERIC_HEADLINE_MARKERS):
        return False
    if not clean_summary or any(
        clean_summary == marker or clean_summary.startswith(marker)
        for marker in _GENERIC_SUMMARY_MARKERS
    ):
        return False
    if not summary_information_gain(clean_headline, clean_summary):
        return False
    if _TRUNCATION_RE.search(clean_headline + clean_summary):
        return False
    if clean_summary.endswith("일정이 공개됐다.") and not _DATE_RE.search(clean_summary):
        return False
    if source_count <= 1 and not official_source and "추가 확인이 필요하다" in clean_summary:
        return False
    return True


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


def _safe_evidence_text(value: str) -> str:
    """Return a snippet only when it is a complete, non-truncated fragment."""

    text = normalize_text(value)
    return "" if _TRUNCATION_RE.search(text) else text


def _fact_evidence_text(value: str) -> str:
    """Keep a concrete lead prefix when only its trailing clause is cut off.

    Search snippets frequently end with an ellipsis after a complete first
    sentence.  That prefix can support a date or action, while the truncated
    tail must remain unusable.  A snippet that starts with an ellipsis has no
    safe prefix and is rejected.
    """

    text = normalize_text(value)
    marker = _TRUNCATION_RE.search(text)
    if not marker:
        return text
    prefix = text[: marker.start()].strip(" ,·-—")
    return prefix if len(prefix) >= 12 else ""


def _fact_lead(item: object) -> str:
    for authority in getattr(item, "authoritative_evidence", ()):
        for value in (getattr(authority, "description", ""), getattr(authority, "title", "")):
            lead = _fact_evidence_text(value)
            if lead:
                return lead
    for value in (getattr(item, "metadata_description", ""), getattr(item, "summary", "")):
        lead = _fact_evidence_text(value)
        if lead:
            return lead
    return ""


def _lineup_detail(evidence: str) -> tuple[str, ...]:
    """Extract only explicit team/player pairs from a complete lineup lead."""

    matches = list(_KBO_TEAM_RE.finditer(evidence))
    pairs: list[str] = []
    for index, team_match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(evidence)
        fragment = evidence[team_match.end() : end]
        fragment = _LINEUP_LABEL_RE.sub("", fragment.lstrip(" \t:：·,/()[]{}-"))
        player_match = _PLAYER_TOKEN_RE.match(fragment)
        if not player_match:
            continue
        player = player_match.group(0).strip("·-—")
        if not player or player in {"경기", "예고", "선발", "투수", "라인업"}:
            continue
        pair = f"{re.sub(r'\s+', ' ', team_match.group(0)).strip()} {player}"
        if pair not in pairs:
            pairs.append(pair)
    return tuple(pairs[:4])


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
    meaningful = tuple(
        value
        for value in values
        if not _DATE_COUNTER_RE.fullmatch(value)
        and not _DATE_STAMP_RE.fullmatch(value)
        and re.search(r"[^\d,.\s]", value)
    )
    if meaningful:
        return meaningful
    if values and all(_DATE_COUNTER_RE.fullmatch(value) or _DATE_STAMP_RE.fullmatch(value) for value in values):
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


def _event_dates(text: str) -> tuple[str, ...]:
    """Extract dates tied to the event, not a publication-date preface."""

    selected: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        matches = list(_DATE_RE.finditer(sentence))
        marker_positions = [
            match.start()
            for marker in _EVENT_DATE_MARKERS
            for match in re.finditer(re.escape(marker), sentence)
        ]
        if matches and marker_positions:
            match = min(matches, key=lambda value: min(abs(value.start() - position) for position in marker_positions))
            selected.append(re.sub(r"\s+", "", match.group(0)))
    return _unique(selected)


def _times(text: str) -> tuple[str, ...]:
    return _unique([re.sub(r"\s+", "", value) for value in _TIME_RE.findall(text)])


def _locations(text: str) -> tuple[str, ...]:
    return _unique([value for value in _LOCATION_TERMS if value.casefold() in text.casefold()])


def _repeated_values(
    items: tuple[object, ...], extractor: Callable[[str], tuple[str, ...]]
) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for item in items:
        # Search descriptions may contain an unrelated trailing clause.  Only
        # repeat facts that appear in the effective headline evidence.
        values = extractor(effective_title(item))
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
    recruitment = recruitment_event_type(text)
    if recruitment:
        return recruitment
    if any(word in text for word in ("실적", "매출", "영업이익", "순이익", "가이던스")):
        return "EARNINGS"
    if any(word in text for word in ("1위", "차트", "관왕", "수상")):
        return "AWARD_CHART"
    if any(word in text for word in ("규제", "법안", "고시", "금지", "허용")):
        return "REGULATION"
    if any(
        word in text
        for word in (
            "정책 발표",
            "정책 결정",
            "정책 시행",
            "정책 개편",
            "대책 발표",
            "대책 시행",
            "규정",
            "기준금리",
            "요구",
            "촉구",
            "줄여라",
        )
    ):
        return "POLICY"
    if any(word in text for word in ("출시", "발매", "선공개", "음원", "신곡", "싱글", "데뷔곡", "신규상장", "상장", "예약판매", "판매 개시", "사양 확정")):
        return "PRODUCT_RELEASE"
    sports_context = any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기", "시구"))
    if (
        sports_context
        and any(word in text for word in ("폭염", "열파"))
        and any(word in text for word in ("중단", "멈춘", "휴식", "재개", "취소"))
    ):
        return "SPORTS_INTERRUPTION"
    if any(contains_action(text, word) for word in ("부상", "트레이드", "엔트리", "선발")):
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
    if any(
        contains_action(text, word)
        for word in ("유치", "투자", "인수", "전략", "데이터센터", "할당", "계약", "생산")
    ):
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
    return next((word for word in _ACTION_MARKERS if contains_action(text, word)), "")


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

    if event_type in {"MARKET", "MARKET_MOVE", "STATISTIC"}:
        clean_title = _clean_headline(title)
        has_fx = any(term in clean_title for term in ("환율", "원달러", "원·달러"))
        has_kospi = "코스피" in clean_title or "KOSPI" in clean_title
        if has_fx and has_kospi:
            first_number = _NUMBER_RE.search(clean_title)
            prefix = clean_title[: first_number.start()] if first_number else clean_title
            if "코스피" in prefix or "KOSPI" in prefix:
                return "코스피"
            if "환율" in prefix or "원달러" in prefix or "원·달러" in prefix:
                return "원·달러 환율"
            return "코스피" if clean_title.find("코스피") < clean_title.find("환율") else "원·달러 환율"
        if has_fx:
            return "원·달러 환율"
        if has_kospi:
            return "코스피"
        if "코스닥" in clean_title or "KOSDAQ" in clean_title:
            return "코스닥"
        if any(term in clean_title for term in ("닛케이", "니케이", "도쿄증시")):
            return "닛케이"
        if "다우" in clean_title:
            return "다우"
        if "나스닥" in clean_title or "NASDAQ" in clean_title:
            return "나스닥"
        if any(term in title for term in ("증시", "주가", "주식")) and subject in {"이젠", "올해", "이번"}:
            return "증시"
    return subject


def _award_subject(title: str, subject: str) -> str:
    """Prefer the named artist/entity over a trailing chart descriptor."""

    clean = _clean_headline(title)
    marker = re.search(r"\s+(?:국내외\s+)?(?:음악\s+)?차트\b", clean)
    if marker:
        candidate = clean[: marker.start()].strip(" ,·-—")
        if len(candidate) >= 2:
            return candidate
    return subject


def _trend_state(topic_id: str, metrics: tuple[TrendMetric, ...]) -> str:
    relevant = [metric for metric in metrics if metric.topic_id == topic_id]
    if not relevant:
        return "비교 부족"
    states = tuple(effective_trend_state(metric) for metric in relevant)
    rising = "RISE" in states
    falling = "FALL" in states
    if rising and falling:
        return "혼조"
    if rising:
        return "상승"
    if falling:
        return "둔화"
    if "INSUFFICIENT_COMPARISON" in states:
        return "비교 부족"
    return "큰 변화 없음"


def _official_source(items: tuple[object, ...]) -> str:
    for item in items:
        authorities = getattr(item, "authoritative_evidence", ())
        for authority in authorities:
            publisher = str(getattr(authority, "publisher", "") or "").strip()
            if publisher:
                return "공식 자료"
        if EvidenceType.OFFICIAL_SOURCE in getattr(item, "provenance", ()):
            return "공식 자료"
        domain = str(getattr(item, "source_domain", ""))
        if is_trusted_official_domain(domain):
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


def _subject_particle(value: str) -> str:
    if not value:
        return "가"
    last = value[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        return "이" if code % 28 else "가"
    return "가"


def _number_with_ro(value: str) -> str:
    """Attach the Korean instrumental marker without producing ``원로``."""

    return f"{value}로" if value.endswith(("%", "달러")) else f"{value}으로"


def _market_direction_sentence(subject: str, marker: str) -> str:
    """Render a direction with the correct Korean predicate form."""

    if marker in {"상승", "하락", "급등", "급락", "증가", "감소", "확대", "축소", "돌파"}:
        return f"{subject}{_particle(subject)} {marker}했다."
    if marker == "보합":
        return f"{subject}{_particle(subject)} 보합세를 보였다."
    return f"{subject}{_particle(subject)} {marker}를 보였다."


def _next_signal(event_type: str, text: str, date: str, action: str) -> str:
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
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
    if event_type == "EARNINGS" and subject:
        period, metric, value = _earnings_fact_parts(cleaned)
        if metric and value:
            fact = " ".join(part for part in (period, metric, value) if part)
            return f"{subject} {fact} 실적"
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and subject and numbers:
        run_phrase = _market_run_phrase(cleaned)
        if run_phrase:
            return f"{subject} {run_phrase}"
        metric_number = _market_metric_number(cleaned, numbers)
        if not metric_number:
            return f"{subject} {change}" if change and change not in _GENERIC_CHANGE_WORDS else subject
        result = f"{subject} {metric_number}"
        # A change fragment from a title without a number is often a clipped
        # article lead (for example ``미 증시 상승 마감에 코스피``).  The
        # metric itself is safe; appending that fragment creates a malformed
        # headline and can imply an unsupported comparison.
        if change and not _NUMBER_RE.search(cleaned) and change not in cleaned:
            change = ""
        for marker in ("강보합세", "강세", "약세", "상승", "하락", "급등", "급락"):
            if marker in change:
                change = marker
                break
        if change and change not in _GENERIC_CHANGE_WORDS and change not in result:
            result += f" · {change}"
        return result
    if event_type == "SPORTS_INTERRUPTION":
        league = "프로야구" if "프로야구" in cleaned or "프로야구" in subject else ("KBO" if "KBO" in cleaned else subject)
        return f"{league} 폭염으로 경기 중단" if league else "폭염으로 경기 중단"
    if event_type in {"AWARD_CHART", "PRODUCT_RELEASE", "INDUSTRY_CHANGE", "REGULATION", "POLICY", "ANNOUNCEMENT"}:
        return cleaned or subject or "주요 변화"
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        if event_type == "SCHEDULED_EVENT" and action in {"발표", "발매", "출시", "공개"} and action in cleaned:
            return _editorial_headline(cleaned, subject=subject)
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
    completion_evidence: str = "",
    market_observation: MetricObservation | None = None,
    market_observations: tuple[MetricObservation, ...] = (),
) -> str:
    if event_type == "EARNINGS" and subject:
        period, metric, value = _earnings_fact_parts(completion_evidence or title)
        if metric and value:
            period_text = f"{period} " if period else ""
            sentence = f"{subject}{_subject_particle(subject)} {period_text}{metric} {value}을 기록했다고 밝혔다."
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and subject:
        summary_subject = "" if _TIME_PREFIX_RE.match(subject) else subject
        summary_subject = _fact_subject(summary_subject)
        observations = tuple(
            observation
            for observation in (market_observations or ((market_observation,) if market_observation else ()))
            if observation.value and observation.direction and observation.direction != "변동"
        )
        if observations:
            sentences: list[str] = []
            for observation in observations[:3]:
                marker = observation.direction
                verb = {"강세": "상승", "약세": "하락"}.get(marker, marker)
                sentence_subject = _fact_subject(observation.instrument or summary_subject)
                sentences.append(
                    f"{sentence_subject}{_particle(sentence_subject)} {observation.value} {verb}했다."
                )
            sentence = " ".join(sentences)
            if completion_evidence:
                # Add one additional, trusted clause when the lead contains
                # a concrete related fact.  Do not paste a generic evidence
                # macro or borrow a second metric's direction.
                detail_parts = re.split(r"(?:했고|하며|지만|그리고|,|，)", completion_evidence)
                detail = next(
                    (
                        part.strip(" ,，:·-—")
                        for part in detail_parts
                        if len(part.strip()) >= 12
                        and not any(
                            marker in part
                            for marker in (
                                "공식 발표와",
                                "여러 보도",
                                "여러 매체",
                                "핵심 내용",
                                "세부 내용",
                            )
                        )
                        and not any(observation.instrument in part for observation in observations)
                    ),
                    "",
                )
                if detail and summary_information_gain(title, detail):
                    sentence += f" {detail.rstrip(' .!?')}."
            if source_count > 1:
                sentence += " 같은 흐름이 여러 보도에서 확인됐다."
            return sentence
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
            marker = next((word for word in _DIRECTIONAL_CHANGE_WORDS if word in change), "")
            if marker == "강보합세" and summary_subject and numbers:
                sentence = f"{summary_subject}{_particle(summary_subject)} {numbers[0]}에서 강보합세를 보였다."
            elif marker and summary_subject and numbers and numbers[0].endswith(("%", "달러", "선")):
                verb = {"강세": "상승", "약세": "하락"}.get(marker, marker)
                if numbers[0].endswith("선"):
                    sentence = f"{summary_subject}{_particle(summary_subject)} {numbers[0]}에서 {verb} 흐름을 보였다."
                else:
                    sentence = f"{summary_subject}{_particle(summary_subject)} {_number_with_ro(numbers[0])} {verb}했다."
            elif marker and summary_subject:
                sentence = _market_direction_sentence(summary_subject, marker)
            else:
                lead = f"{summary_subject}의 " if summary_subject else ""
                if numbers:
                    sentence = f"{lead}{numbers[0]} 수치가 "
                    sentence += "여러 보도에서 확인됐다." if source_count > 1 else "한 건의 보도에서 제시됐다. 추가 확인이 필요하다."
                else:
                    sentence = ""
        elif source_count > 1:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 여러 보도에서 확인됐다." if numbers else ""
        else:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 한 건의 보도에서 제시돼 추가 확인이 필요하다." if numbers else ""
    elif event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        event_phrase = action if action in _EVENT_ACTIONS else ""
        if any(marker in completion_evidence for marker in _COMPLETION_MARKERS):
            if event_type == "ENTERTAINMENT_EVENT" and event_phrase == "컴백":
                duration_match = re.search(r"\d+\s?년만", title)
                duration = duration_match.group(0).replace("만", " 만에") if duration_match else ""
                season = "여름" if "여름" in title else ""
                detail = " ".join(value for value in (duration, season) if value)
                sentence = f"{subject}{_subject_particle(subject)} {detail + ' ' if detail else ''}컴백 활동을 마쳤다."
            else:
                when = f"{date} " if date else ""
                where = f"{location} " if location else ""
                event_noun = event_phrase or "행사"
                particle = "이" if event_noun == "컴백" else "가"
                sentence = f"{subject}의 {when}{where}{event_noun}{particle} 성황리에 진행됐다."
        elif event_type == "ENTERTAINMENT_EVENT" and ("컴백" in title or action == "컴백") and date:
            sentence = f"{subject}가 {date} 컴백한다."
        elif event_type == "ENTERTAINMENT_EVENT" and ("앨범" in title or action == "발매") and date:
            sentence = f"{subject}가 {date} 앨범을 발매한다."
        elif date or location:
            when = f"{date} " if date else ""
            where = f"{location}에서 " if location else ""
            phrase = f"{event_phrase} 일정이" if event_phrase else "일정이"
            sentence = f"{subject} {phrase} {when}{where}예정돼 있다."
        else:
            if event_phrase == "컴백":
                sentence = f"{subject}의 컴백이 확인됐다."
            elif event_phrase:
                sentence = f"{subject}의 {event_phrase} 소식이 확인됐다."
            else:
                sentence = f"{subject}의 행사 소식이 확인됐다."
    elif event_type in {"POLICY", "REGULATION"} and subject:
        detail = normalize_text(completion_evidence)
        normalized_title = normalize_text(title)
        if normalized_title and detail.startswith(normalized_title):
            detail = detail[len(normalized_title) :].strip(" ,:·-—")
        if (
            len(detail) >= 20
            and not _TRUNCATION_RE.search(detail)
            and not any(marker in detail for marker in _GENERIC_SUMMARY_MARKERS)
            and summary_information_gain(title, detail)
        ):
            sentence = detail.rstrip(" .!?。！") + "."
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        policy_action = action if action in {"발표", "공개", "시행", "고시", "확정", "요구", "촉구", "줄여라"} else "정책 변화"
        if policy_action in {"요구", "촉구", "줄여라"}:
            sentence = f"{_clean_headline(title)}."
        else:
            sentence = f"{subject}의 {policy_action} 내용이 확인됐다."
    elif event_type == "PRODUCT_RELEASE" and subject:
        release_subject = subject or _clean_headline(title).split(",", 1)[0].strip()
        listing = re.search(
            r"(?:오는\s*)?(\d{1,2}\s?일)\s*상장\s*예정인\s*([A-Za-z0-9가-힣·&+\- ]+?(?:ETF|펀드))",
            completion_evidence,
        )
        if listing:
            listing_date, listing_product = listing.groups()
            sentence = f"{listing_product.strip()}{_subject_particle(listing_product.strip())} {listing_date} 상장될 예정이다."
        elif "상장" in title and date:
            sentence = f"{release_subject}{_subject_particle(release_subject)} {date} 상장될 예정이다."
        elif date and not any(marker in title for marker in ("데뷔곡", "앨범", "음원", "싱글", "신곡", "발매")):
            sentence = f"{release_subject}{_subject_particle(release_subject)} {date} 출시된다."
        elif "일정" in completion_evidence and not date:
            sentence = f"{release_subject}의 출시 일정이 공개됐다."
        else:
            if "데뷔곡" in title:
                release_noun, release_verb, release_fact = "데뷔곡", "발매", "데뷔곡 발매"
            elif "앨범" in title:
                release_noun, release_verb, release_fact = "앨범", "발매", "앨범 발매"
            elif any(marker in title for marker in ("음원", "싱글", "신곡", "발매")):
                release_noun, release_verb, release_fact = "신곡", "발매", "신곡 발매"
            elif "도구" in title or "서비스" in title:
                release_noun, release_verb, release_fact = "도구·서비스", "출시", "도구·서비스 출시"
            else:
                release_noun, release_verb, release_fact = "제품", "출시", "출시"
            if date and release_verb == "발매":
                sentence = f"{release_subject}{_subject_particle(release_subject)} {date} {release_noun}을 {release_verb}한다."
            elif date and release_verb == "출시":
                sentence = f"{release_subject}{_subject_particle(release_subject)} {date} {release_noun}을 {release_verb}한다."
            else:
                sentence = f"{release_subject}의 {release_fact} 소식이 확인됐다."
    elif event_type == "AWARD_CHART" and subject:
        chart_number = next((value for value in numbers if value.endswith("위")), "")
        music_context = any(
            marker in title for marker in ("음악", "음원", "앨범", "가요", "아이돌", "가수", "차트", "빌보드", "멜론", "노래")
        )
        if chart_number and music_context:
            sentence = f"{subject}가 음악 차트 {chart_number}에 올랐다."
        elif chart_number:
            sentence = f"{_clean_headline(title)}."
        else:
            sentence = f"{_clean_headline(title)}."
    elif event_type.startswith("RECRUITMENT") and subject:
        ratio_match = re.search(r"\d+(?:\.\d+)?\s?대\s?\d+", f"{title} {completion_evidence}")
        counts_match = re.search(
            r"([\d,]+명)\s*선발.*?([\d,]+명)\s*(?:이|가|을|를)?\s*지원",
            completion_evidence,
        )
        if counts_match and ratio_match:
            selected, applicants = counts_match.groups()
            ratio = re.sub(r"\s+", "", ratio_match.group(0))
            sentence = f"{subject} {ratio} 경쟁률을 기록했고, {selected} 선발에 {applicants} 지원했다."
        elif counts_match:
            selected, applicants = counts_match.groups()
            sentence = f"{subject} 공채에서 {selected} 선발에 {applicants} 지원했다."
        elif ratio_match:
            sentence = f"{subject} 공채 경쟁률은 {re.sub(r'\s+', '', ratio_match.group(0))}였다."
        else:
            sentence = ""
        if not sentence:
            sentence = f"{_clean_headline(title)}."
    elif event_type == "INDUSTRY_CHANGE" and subject:
        change_action = {
            "유치": "투자 유치" if any(marker in title for marker in ("투자", "자금", "출자")) else "유치",
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
        if action == "유치" and change_action == "유치":
            sentence = f"{_clean_headline(title)}."
        elif key_number:
            sentence = f"{subject}의 {key_number} 규모 {change_action} 소식이 보도됐다."
        else:
            detail = completion_evidence
            if title and detail.startswith(title):
                detail = detail[len(title) :].strip(" ,:·-—")
            sentence = detail if len(detail) >= 12 else ""
    elif event_type == "ROSTER_PERSONNEL" and subject:
        if action == "선발":
            lineup = _lineup_detail(completion_evidence)
            if len(lineup) >= 2:
                detail = "과 ".join(lineup[:2])
                context = " ".join(part for part in (date, location) if part)
                context = f"{context} 경기의 " if context else "경기의 "
                sentence = f"{context}선발로 {detail}{_subject_particle(detail)} 예고됐다."
            else:
                sentence = ""
        else:
            sentence = ""
        if not sentence:
            clean_title = _clean_headline(title)
            if numbers and clean_title:
                sentence = f"{clean_title}."
            else:
                action_text = action or "선수단 변동"
                sentence = f"{subject}의 {action_text}{_subject_particle(action_text)} 확인됐다."
    elif event_type == "SPORTS_RESULT" and subject:
        detail = normalize_text(completion_evidence)
        if detail.startswith(normalize_text(title)):
            detail = detail[len(normalize_text(title)) :].strip(" ,:·-—")
        if detail and not _TRUNCATION_RE.search(detail) and len(detail) >= 12:
            sentence = detail.rstrip(" .!?") + "."
        else:
            score_match = re.search(r"\d+\s*[-대]\s*\d+", title)
            if score_match:
                result_word = "승리" if "승리" in title else "패배" if "패배" in title else "경기 결과"
                sentence = f"{subject}의 {result_word} 스코어는 {re.sub(r'\s+', '', score_match.group(0))}로 기록됐다."
            else:
                sentence = ""
    elif event_type == "SPORTS_INTERRUPTION" and subject:
        evidence = f"{title} {completion_evidence}".casefold()
        league = "프로야구" if "프로야구" in evidence or "프로야구" in subject.casefold() else ("KBO" if "kbo" in evidence else subject)
        if "재개" in evidence and ("중단" in evidence or "취소" in evidence or "휴식" in evidence):
            resume_date = f"{date}에 " if date else ""
            sentence = f"{league} 경기가 폭염으로 중단된 뒤 {resume_date}재개됐다."
        elif "취소" in evidence:
            sentence = f"{league} 경기가 폭염 영향으로 취소됐다."
        elif "휴식" in evidence:
            sentence = f"{league} 경기가 폭염 영향으로 휴식기에 들어갔다."
        else:
            sentence = f"{league} 경기가 폭염 영향으로 중단됐다."
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


def _evidence_summary(summary: str) -> str:
    """Expose a story-specific fact, never a repeated evidence macro."""

    return normalize_text(summary)


def synthesize_cluster(
    cluster: StoryCluster,
    *,
    topic_name: str,
    trend_metrics: tuple[TrendMetric, ...],
    event_type_override: str | None = None,
    event_signature_override: str | None = None,
    conflict_state_override: str | None = None,
) -> tuple[str, str, str, tuple[str, ...], StoryFacts, Certainty]:
    items = cluster.items
    representative = cluster.representative
    headline_item = best_headline_item(items)
    title = effective_title(headline_item) or _clean_headline(headline_item.title)
    headline_evidence = " ".join(
        value for value in (effective_title(headline_item), effective_lead(headline_item)) if value
    )
    fact_headline_evidence = " ".join(
        value for value in (effective_title(headline_item), _fact_lead(headline_item)) if value
    )
    title_evidence = " ".join(effective_title(item) for item in items if effective_title(item))
    repeated_numbers = _repeated_values(items, _numbers)
    repeated_dates = _repeated_values(items, _dates)
    repeated_times = _repeated_values(items, _times)
    repeated_locations = _repeated_values(items, _locations)
    numbers = _unique(list(_numbers(headline_evidence)) + list(repeated_numbers))
    display_numbers = _meaningful_numbers(numbers, title)
    metadata_dates = _unique(
        [date for item in items for date in _event_dates(safe_evidence_text(item.metadata_description))]
    )
    dates = _unique(
        list(_dates(effective_title(headline_item)))
        + list(_event_dates(_fact_lead(headline_item)))
        + list(repeated_dates)
        + list(metadata_dates)
    )
    times = _unique(list(_times(headline_evidence)) + list(repeated_times))
    locations = _unique(
        list(_locations(headline_evidence))
        + list(_locations(fact_headline_evidence))
        + list(repeated_locations)
    )
    # Classify the representative headline first. Descriptions may mention
    # generic words such as "정책" or "공개" while the headline carries the
    # actual subject (for example a market statistic). This keeps the
    # synthesis anchored to the strongest visible evidence.
    title_event_type = _event_type(title, _numbers(title))
    lead_event_type = _event_type(effective_lead(headline_item), _numbers(effective_lead(headline_item)))
    inferred_event_type = title_event_type if title_event_type != "OTHER" else (
        lead_event_type if lead_event_type != "OTHER" else _event_type(title_evidence, numbers)
    )
    # Production selection already has the editorial event gate. Reuse that
    # decision for synthesis so the audit and the emitted StoryFacts cannot
    # diverge when two deterministic classifiers have different precedence.
    event_type = event_type_override or inferred_event_type
    market_observations = metric_observations(title)
    market_observation = next(iter(market_observations), None)
    # Do not borrow an action from another headline in a broad cluster. A
    # secondary article may describe a different event while sharing the
    # same entity or theme. Market stories need a market outcome as their
    # action; an explanatory phrase such as ``금리 인상`` is not that
    # outcome.
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        action = (
            next((observation.direction for observation in market_observations if observation.direction), "")
            or market_direction(title)
        )
    elif event_type.startswith("RECRUITMENT"):
        # Recruitment competition/result stories frequently carry a lead
        # verb such as ``공개``. The taxonomy already expresses the event;
        # do not promote that incidental verb into StoryFacts.action.
        action = ""
    else:
        action = _action(title) or _action(effective_lead(headline_item))
    if event_type == "SPORTS_INTERRUPTION":
        interruption_evidence = headline_evidence.casefold()
        subject = "프로야구" if any(term in interruption_evidence for term in ("프로야구", "kbo", "야구")) else "KBO"
        if "재개" in interruption_evidence:
            action = "재개"
        elif any(term in interruption_evidence for term in ("중단", "멈춘", "취소", "휴식", "방학")):
            action = "중단"
    else:
        earnings_observation = next(iter(earnings_observations(title)), None) if event_type == "EARNINGS" else None
        if earnings_observation is not None:
            # Reuse the bound earnings observation so a period such as
            # ``2026년`` cannot be mistaken for part of the company name.
            subject = earnings_observation.instrument
            display_numbers = _unique(
                [value for value in (earnings_observation.period, earnings_observation.value) if value]
            )
        else:
            subject = _domain_subject(title, _subject(title, action, display_numbers), event_type)
        if event_type == "AWARD_CHART":
            subject = _award_subject(title, subject)
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        if market_observations:
            # Keep each metric bound to its own instrument and direction.
            display_numbers = tuple(observation.value for observation in market_observations[:3])
        else:
            # Numbers found only in a market lead may be a time, comparison
            # context, or another entity's value. Without a bound observation
            # they are not all safe display facts. Retain only values with a
            # meaningful market unit; bare publication-time counters are not
            # facts about the market move.
            display_numbers = tuple(
                value
                for value in _meaningful_numbers(numbers, title)
                if not _TIME_COUNTER_RE.fullmatch(value)
            )
        if market_observation is not None:
            change = market_observation.direction or action
            if market_observation.instrument:
                subject = market_observation.instrument
        else:
            change = (
                _tail_after_first_number(title, display_numbers)
                or (_change_phrases(title)[:1] or ("",))[0]
                or action
            )
    else:
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
    numeric_values = repeated_numbers
    # Keep all headline numbers for conflict detection, while only repeated
    # or representative numbers are eligible for display facts.
    all_numeric = _unique(list(_numbers(title_evidence)))
    if len(numeric_values) == 0 and len(all_numeric) > 1 and event_type in {"STATISTIC", "MARKET", "EARNINGS"}:
        units = {re.sub(r"[\d,.\s]", "", value) for value in all_numeric}
        if len(units) == 1:
            uncertainty = "보도마다 수치가 달라 추가 확인이 필요하다."
    official = _official_source(items)
    source_count = cluster.source_count
    trend_state = _trend_state(cluster.topic_id, trend_metrics)
    canonical_date, date_conflict = canonical_event_date(title, _fact_lead(headline_item))
    date = canonical_date or (dates[0] if dates else "")
    location = locations[0] if locations else ""
    next_signal = _next_signal(event_type, headline_evidence, date, action)
    conflict_state = conflict_state_override or "NO_CONFLICT"
    if date_conflict:
        conflict_state = "DATE_CONFLICT"
    temporal_state = ""
    if event_type == "SPORTS_INTERRUPTION":
        combined = f"{title} {fact_headline_evidence}".casefold()
        if "재개" in combined:
            temporal_state = "RESUMING" if "예정" in combined else "RESUMED"
        elif "취소" in combined:
            temporal_state = "CANCELLED"
        elif "중단" in combined or "멈춘" in combined:
            temporal_state = "INTERRUPTED"
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
            (
                [action]
                if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and action
                else [change]
                if len(market_observations) <= 1 and change
                else [
                    f"{observation.instrument} {observation.direction}"
                    for observation in market_observations[:3]
                    if observation.direction
                ]
            )
            + (
                []
                if market_observation is not None
                else list(_change_phrases(" ".join(_clean_headline(getattr(item, "title", "")) for item in items)))
            )
        )[:3],
        official_source=official,
        source_count=source_count,
        source_diversity=source_count,
        repeated_facts=repeated[:3],
        unique_facts=unique_facts[:3],
        trend_state=trend_state,
        next_known_event=next_signal,
        uncertainty=uncertainty,
        event_signature=event_signature_override
        or canonical_event_signature(event_type, title, lead=_fact_lead(headline_item), subject=subject, action=action),
        conflict_state=conflict_state,
        temporal_state=temporal_state,
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
        fact_headline_evidence,
        market_observation=market_observation,
        market_observations=market_observations,
    )
    evidence = _evidence_summary(summary)
    watch = (next_signal,) if next_signal else ()
    corroborated, _ = evidence_corroborated(items)
    if corroborated or official:
        certainty = Certainty.CONFIRMED
    elif event_type != "OTHER" and (numbers or dates or action):
        certainty = Certainty.SUPPORTED_SINGLE_SOURCE
    else:
        certainty = Certainty.UNCERTAIN
    return headline, summary, evidence, watch, facts, certainty
