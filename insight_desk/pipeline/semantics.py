"""Small, shared semantic primitives used by editorial pipeline stages.

The project deliberately stays deterministic.  These helpers do not attempt
to understand every Korean sentence; they protect the boundaries that are
unsafe to infer from search snippets and keep the same event facts together
when clustering, synthesis, and audit inspect a candidate.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

from .normalization import normalize_text


ACTION_TERMS: tuple[str, ...] = (
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
    "트레이드",
    "부상",
    "승리",
    "패배",
    "컴백",
    "전략",
    "할당",
    "계약",
    "상승",
    "하락",
    "증가",
    "감소",
    "변동",
    "급등",
    "급락",
    "강세",
    "약세",
)

_ACTION_SUFFIXES = (
    "됐다",
    "된다",
    "했다",
    "한다",
    "하며",
    "하고",
    "하는",
    "하여",
    "된",
    "될",
    "돼",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "도",
    "만",
    "와",
    "과",
    "에",
    "에서",
    "으로",
    "로",
)
_ACTION_COMPOUND_SUFFIXES: dict[str, tuple[str, ...]] = {
    # These are domain terms whose compound form still names the same
    # action (``선발투수``), unlike collision-prone forms such as
    # ``NH투자증권`` or ``장기투자``.
    "선발": ("투수", "라인업"),
}
_ACTION_SUFFIX_PATTERN = "(?:" + "|".join(map(re.escape, _ACTION_SUFFIXES)) + ")?"
_WORD_CHAR = r"가-힣A-Za-z0-9"

_DATE_RE = re.compile(
    r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)"
)
_ISO_DATE_RE = re.compile(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}")
_EVENT_DATE_MARKERS = (
    "발매",
    "출시",
    "컴백",
    "공개",
    "발표",
    "개최",
    "공연",
    "콘서트",
    "진행",
    "시작",
    "재개",
    "예정",
    "상장",
    "시구",
    "경기",
    "시험",
    "접수",
    "선발",
    "합격",
)

_NUMBER_RE = re.compile(
    r"[+-]?\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|개월|주년|원대|원|%|퍼센트|명|건|배|개|곳|일|월|년|분|시|위|점|대|선|km))?"
)
_DIRECTION_RE = re.compile(
    r"(?:소폭\s*)?(?:급등|급락|상승|하락|강세|약세|강보합세|보합|증가|감소|확대|축소|돌파|변동)"
)
_MARKET_INSTRUMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("코스피", ("코스피", "KOSPI")),
    ("코스닥", ("코스닥", "KOSDAQ")),
    ("원·달러 환율", ("원·달러 환율", "원달러 환율", "환율")),
    ("국고채 금리", ("국고채 금리", "국채 금리", "국고채", "국채선물", "국채")),
    ("엔화", ("엔화",)),
    ("닛케이", ("닛케이225", "니케이225", "닛케이", "니케이", "도쿄증시")),
    ("다우", ("다우존스", "다우")),
    ("나스닥", ("나스닥", "NASDAQ")),
    ("S&P500", ("S&P500", "S&P 500")),
    ("삼성전자", ("삼성전자",)),
    ("SK하이닉스", ("SK하이닉스", "하이닉스")),
)

_MARKET_DIRECTION_TERMS: tuple[str, ...] = (
    "강보합세",
    "급등",
    "급락",
    "상승",
    "하락",
    "강세",
    "약세",
    "보합",
    "증가",
    "감소",
    "확대",
    "축소",
    "돌파",
    "변동",
)
_MARKET_DIRECTION_ALIASES: tuple[tuple[str, str], ...] = (
    ("올랐다", "상승"),
    ("올라", "상승"),
    ("오른", "상승"),
    ("내렸다", "하락"),
    ("내려", "하락"),
    ("내린", "하락"),
)


def fold(value: str) -> str:
    return unicodedata.normalize("NFKC", normalize_text(value)).casefold()


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", fold(value))


def canonical_publisher(publisher: str = "", domain: str = "") -> str:
    """Return one stable identity for publisher/domain diversity accounting."""

    raw_domain = normalize_text(domain).casefold()
    if raw_domain:
        candidate = raw_domain if "://" in raw_domain else f"https://{raw_domain}"
        host = urlsplit(candidate).hostname or raw_domain
        host = host.removeprefix("www.").rstrip(".")
        if host:
            return host
    value = re.sub(r"\s+", " ", normalize_text(publisher)).strip().casefold()
    value = re.sub(r"^(?:주식회사|㈜|\(주\))\s*", "", value)
    return value


def contains_boundary_term(text: str, term: str) -> bool:
    """Match a lexical term without matching inside a Korean compound.

    The optional particle/verb suffixes preserve ordinary forms such as
    ``투자는`` and ``부상했다`` while rejecting ``보부상``, ``장기투자``, and
    ``NH투자증권``.
    """

    value = normalize_text(text)
    phrase = normalize_text(term)
    if not value or not phrase:
        return False
    if " " in phrase:
        pattern = rf"(?<![{_WORD_CHAR}]){re.escape(phrase)}(?![{_WORD_CHAR}])"
        return bool(re.search(pattern, value, re.IGNORECASE))
    compound_suffix = _ACTION_COMPOUND_SUFFIXES.get(phrase, ())
    compound_pattern = "|".join(re.escape(value) for value in compound_suffix)
    suffix_pattern = _ACTION_SUFFIX_PATTERN
    if compound_pattern:
        suffix_pattern = rf"(?:{suffix_pattern}|{compound_pattern})"
    pattern = rf"(?<![{_WORD_CHAR}]){re.escape(phrase)}{suffix_pattern}(?![{_WORD_CHAR}])"
    return bool(re.search(pattern, value, re.IGNORECASE))


def contains_action(text: str, term: str) -> bool:
    return contains_boundary_term(text, term)


def first_action(text: str, terms: tuple[str, ...] = ACTION_TERMS) -> str:
    return next((term for term in terms if contains_action(text, term)), "")


def contains_intent_term(text: str, term: str) -> bool:
    """Use strict boundaries for short/high-collision intent vocabulary."""

    phrase = normalize_text(term)
    if len(compact(phrase)) <= 3 or compact(phrase) in {
        "투자",
        "한화",
        "차트",
        "아이돌",
        "kbo",
        "psat",
    }:
        return contains_boundary_term(text, phrase)
    # Longer domain nouns retain bounded substring recall for forms such as
    # ``반도체주`` and ``공무원시험``.
    return compact(phrase) in compact(text)


@dataclass(frozen=True)
class MetricObservation:
    instrument: str
    metric: str
    value: str
    direction: str
    period: str = ""
    raw: str = ""


def _instrument_matches(text: str) -> list[tuple[int, int, str]]:
    matches: list[tuple[int, int, str]] = []
    for instrument, aliases in _MARKET_INSTRUMENTS:
        for alias in aliases:
            for match in re.finditer(re.escape(alias), text, re.IGNORECASE):
                matches.append((match.start(), match.end(), instrument))
    # Prefer the longest alias at a position (``원·달러 환율`` over ``환율``)
    # and keep the input order for different instruments.
    matches.sort(key=lambda value: (value[0], -(value[1] - value[0])))
    selected: list[tuple[int, int, str]] = []
    for match in matches:
        if any(match[0] < other[1] and other[0] < match[1] for other in selected):
            continue
        selected.append(match)
    return sorted(selected)


def metric_observations(text: str) -> tuple[MetricObservation, ...]:
    """Extract independently bound market observations from one headline."""

    value = normalize_text(text)
    instruments = _instrument_matches(value)
    observations: list[MetricObservation] = []
    for index, (start, end, instrument) in enumerate(instruments):
        segment_end = instruments[index + 1][0] if index + 1 < len(instruments) else len(value)
        segment = value[end:segment_end]
        # A clause delimiter is a safer boundary than borrowing a number from
        # a later comparison clause.
        segment = re.split(r"[;；。!?]", segment, maxsplit=1)[0]
        number_match = _NUMBER_RE.search(segment[:80])
        if not number_match:
            continue
        number = re.sub(r"\s+", "", number_match.group(0))
        direction_match = _DIRECTION_RE.search(segment[number_match.end() : number_match.end() + 32])
        if direction_match is None:
            direction_match = _DIRECTION_RE.search(segment[:80])
        direction = direction_match.group(0).replace(" ", "") if direction_match else ""
        observations.append(
            MetricObservation(
                instrument=instrument,
                metric="CHANGE" if direction else "LEVEL",
                value=number,
                direction=direction,
                raw=value[start:segment_end].strip(" ,·-—"),
            )
        )
    return tuple(observations)


def market_instruments(text: str) -> tuple[str, ...]:
    """Return distinct market instruments named in trusted text order."""

    return tuple(dict.fromkeys(instrument for _, _, instrument in _instrument_matches(normalize_text(text))))


def metric_summary_preserves_entity_binding(headline: str, summary: str) -> bool:
    """Require every headline metric entity to survive in the summary.

    A headline naming multiple instruments is safe only when each instrument
    has a bound numeric observation.  Otherwise the renderer cannot know
    which direction or value belongs to which entity and must reject the
    candidate instead of selecting one metric arbitrarily.
    """

    headline_instruments = market_instruments(headline)
    if not headline_instruments:
        return True
    observations = metric_observations(headline)
    if len(headline_instruments) > 1 and not observations:
        return False
    summary_instruments = set(market_instruments(summary))
    return set(headline_instruments).issubset(summary_instruments)


def market_direction(text: str) -> str:
    """Return a market direction without confusing it with rate actions.

    ``금리 인상 우려 완화에 코스피 강보합세`` contains both a policy
    phrase and a market outcome.  The latter is the event action for a
    market story; generic action extraction must not promote ``인상``.
    """

    value = normalize_text(text)
    matches = [
        (match.start(), match.end(), term)
        for term in _MARKET_DIRECTION_TERMS
        for match in re.finditer(re.escape(term), value)
    ]
    if not matches:
        matches.extend(
            (match.start(), match.end(), canonical)
            for term, canonical in _MARKET_DIRECTION_ALIASES
            for match in re.finditer(re.escape(term), value)
        )
    if not matches:
        return ""
    # ``보합`` is contained in ``강보합세``. Keep the longest lexical match
    # at an overlapping position before choosing the latest direction.
    filtered = [
        current
        for current in matches
        if not any(
            len(other[2]) > len(current[2])
            and other[0] <= current[0]
            and other[1] >= current[1]
            for other in matches
        )
    ]
    return max(filtered, key=lambda item: (item[0], len(item[2])))[2]


def market_direction_class(text: str) -> str:
    """Normalize market direction into up/down/neutral for conflict checks."""

    direction = market_direction(text)
    if direction in {"강보합세", "보합"}:
        return "NEUTRAL"
    if direction in {"급등", "상승", "강세", "증가", "확대", "돌파"}:
        return "UP"
    if direction in {"급락", "하락", "약세", "감소", "축소"}:
        return "DOWN"
    return ""


def event_dates(text: str) -> tuple[str, ...]:
    """Return only dates close to an event marker in trusted evidence."""

    value = normalize_text(text)
    result: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", value):
        matches = list(_DATE_RE.finditer(sentence))
        if not matches:
            continue
        markers = [
            match.start()
            for marker in _EVENT_DATE_MARKERS
            for match in re.finditer(re.escape(marker), sentence)
        ]
        if not markers:
            continue
        match = min(matches, key=lambda item: min(abs(item.start() - marker) for marker in markers))
        result.append(re.sub(r"\s+", "", match.group(0)))
    return tuple(dict.fromkeys(result))


def canonical_event_date(title: str, lead: str = "") -> tuple[str, bool]:
    """Prefer the title event date and flag disagreement with its lead."""

    title_dates = event_dates(title)
    lead_dates = event_dates(lead)
    if title_dates and lead_dates and not set(title_dates).intersection(lead_dates):
        return title_dates[0], True
    return (title_dates or lead_dates or ("",))[0], False


def recruitment_event_type(text: str) -> str:
    """Classify civil-service events separately from sports personnel events."""

    value = fold(text)
    recruitment = any(
        contains_boundary_term(value, term)
        for term in ("공채", "채용", "공무원", "시험", "원서접수", "합격자", "인사혁신처")
    )
    if not recruitment:
        return ""
    if (
        contains_boundary_term(value, "경쟁률")
        or contains_boundary_term(value, "지원자")
        or contains_boundary_term(value, "지원")
    ):
        return "RECRUITMENT_COMPETITION"
    if contains_boundary_term(value, "합격") or contains_boundary_term(value, "선발"):
        return "RECRUITMENT_RESULT"
    if any(contains_boundary_term(value, term) for term in ("시험 일정", "시험일", "원서접수", "일정", "공고")):
        return "RECRUITMENT_SCHEDULE"
    return "RECRUITMENT_APPLICATION"


def canonical_event_signature(
    event_type: str,
    title: str,
    *,
    lead: str = "",
    subject: str = "",
    action: str = "",
) -> str:
    """Build a stable, fact-bound signature for novelty and audit."""

    date, date_conflict = canonical_event_date(title, lead)
    observations = metric_observations(title)
    if observations and event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        bound = ";".join(
            ":".join(part for part in (observation.instrument, observation.metric, observation.value, observation.direction) if part)
            for observation in observations[:3]
        )
        parts = (event_type, bound, date)
        return "|".join(part for part in parts if part)
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9가-힣·]{2,}", fold(title))
        if token not in {"관련", "보도", "소식", "기사", "주요", "뉴스", "확인", "발표"}
    ]
    parts = [event_type]
    if subject:
        parts.append(compact(subject))
    if action:
        parts.append(compact(action))
    parts.extend(tokens[:8])
    if date:
        parts.append(date)
    if date_conflict:
        parts.append("DATE_CONFLICT")
    return "|".join(dict.fromkeys(part for part in parts if part))


def summary_information_gain(headline: str, summary: str) -> bool:
    """Require summary content to carry a role beyond headline punctuation."""

    def semantic_tokens(value: str) -> set[str]:
        suffixes = (
            "으로", "에서", "했다", "됐다", "한다", "된다", "하며", "하고", "하는", "하여",
            "은", "는", "이", "가", "을", "를", "의", "도", "만", "에", "로",
        )
        tokens = set(re.findall(r"[A-Za-z0-9가-힣]{2,}", fold(value)))
        normalized: set[str] = set()
        for token in tokens:
            value = token
            for suffix in suffixes:
                if value.endswith(suffix) and len(value) > len(suffix) + 1:
                    value = value[: -len(suffix)]
                    break
            normalized.add(value)
        return normalized

    headline_tokens = semantic_tokens(headline)
    summary_tokens = semantic_tokens(summary)
    if not headline_tokens or not summary_tokens:
        return False
    if compact(headline).rstrip(".") == compact(summary).rstrip("."):
        return False
    additional = summary_tokens - headline_tokens
    # A particle or a single reporting verb is not an editorial fact.  A
    # number/date, a named result, or at least two new lexical tokens is.
    meaningful_additional = {
        token
        for token in additional
        if token not in {
            "은", "는", "이", "가", "을", "를", "의", "및", "소식", "내용", "확인", "보도",
            "됐다", "했다", "발표", "공개", "출시", "소식", "관련",
        }
    }
    return bool(meaningful_additional or any(char.isdigit() for char in summary if char not in headline))
