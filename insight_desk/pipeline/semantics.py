"""Small, shared semantic primitives used by editorial pipeline stages.

The project deliberately stays deterministic.  These helpers do not attempt
to understand every Korean sentence; they protect the boundaries that are
unsafe to infer from search snippets and keep the same event facts together
when clustering, synthesis, and audit inspect a candidate.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from ..domain.models import TemporalFact
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
    "해서",
    "해",
    "한",
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
_AUDIENCE_TARGET_RE = re.compile(
    r"\s+(?:(?:전|전체|모든)\s*)?"
    r"(?:직원|시민|주민|학생|고객|사용자|회원|관객|교사|장병|국민|기업|가구|환자)"
    r"\s*대상(?:으로|은|는|이|가|을|를)?$"
)

_DATE_RE = re.compile(
    r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)"
)
_ISO_DATE_RE = re.compile(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}")
_RELATIVE_DATE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:어제|오늘|내일|모레)(?![가-힣A-Za-z0-9])"
)
_DURATION_VALUE = r"(?:\d+\s*일|하루|이틀|사흘|나흘|닷새|엿새|일주일)"
_DURATION_RE = re.compile(rf"(?P<value>{_DURATION_VALUE})\s*(?:동안|간|째)")
_ELAPSED_DURATION_RE = re.compile(rf"(?P<value>{_DURATION_VALUE})\s*(?:만에|후|뒤)")
_RESUMPTION_MARKERS = ("재개", "다시 시작", "다시 문", "문을 열")
_INTERRUPTION_MARKERS = ("중단", "멈춘", "멈춰", "휴식", "취소")
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
    r"[+-]?\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|개월|주년|원대|원|%|퍼센트|명|건|배|개|종|곳|일|월|년|분|시|위|점|대|선|km))?"
)
_PERIOD_RE = re.compile(
    r"(?:20\d{2}\s?년\s?)?(?:\d{1,2}\s?월|[1-4]\s?분기|상반기|하반기|연간|월간|분기|전년(?:동월)?|전월)"
)
_EARNINGS_PERIOD_RE = re.compile(r"(?:20\d{2}\s?년\s?)?(?:[1-4]\s?분기|상반기|하반기|연간)")
_EARNINGS_METRIC_RE = re.compile(
    r"(?:영업이익|영업손실|매출액|매출|당기순이익|순이익|순손실|가이던스)"
)
_EARNINGS_VALUE_RE = re.compile(
    r"(?<![A-Za-z가-힣])\d[\d,.]*\s?(?:조원|억원|만원|천만원|만\s?달러|억\s?달러|달러|원|%|퍼센트)"
)
_RECRUITMENT_RATIO_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?\s*대\s*1(?!\d)")
_EARNINGS_DESCRIPTOR_RE = re.compile(
    r"\s+(?:(?:AI|GPU|클라우드|반도체|신사업)\s+)*(?:성과|효과|기반|관련|전략|사업|성장|호조|부진|개선|전망|영향|대비)"
    r"(?:로|으로|에|을|를|이|가|은|는)?\s*$",
    re.IGNORECASE,
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
_CORPORATE_MARKET_INSTRUMENTS = frozenset({"삼성전자", "SK하이닉스"})
_CORPORATE_MARKET_CONTEXT = (
    "주가",
    "주식",
    "증시",
    "시가총액",
    "시총",
    "거래",
    "코스피",
    "코스닥",
    "상승",
    "하락",
    "급등",
    "급락",
    "강세",
    "약세",
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

TRUSTED_OFFICIAL_DOMAINS = frozenset(
    {
        "bok.or.kr",
        "kosis.kr",
        "opendart.fss.or.kr",
        "dart.fss.or.kr",
        "fss.or.kr",
        "kostat.go.kr",
        "mpm.go.kr",
        "gosi.kr",
        "koreabaseball.com",
        "hanwhaeagles.co.kr",
        "openai.com",
        "blog.google",
        "hybecorp.com",
        "smentertainment.com",
        "jype.com",
    }
)


def is_trusted_official_domain(domain: str) -> bool:
    """Accept only explicitly registered official hosts.

    Government TLDs alone are not an authority proof: a random ``.go.kr`` or
    ``.or.kr`` host must not turn a news item into official evidence.
    """

    raw = normalize_text(domain).casefold()
    if not raw:
        return False
    candidate = raw if "://" in raw else f"https://{raw}"
    host = (urlsplit(candidate).hostname or raw).removeprefix("www.").rstrip(".")
    return any(host == trusted or host.endswith(f".{trusted}") for trusted in TRUSTED_OFFICIAL_DOMAINS)

_EVENT_ACTION_CONTRACTS: dict[str, tuple[str, ...]] = {
    "REGULATION": ("규제", "법안", "고시", "허용", "금지", "시행", "제도 개편"),
    "POLICY": (
        "정책 발표",
        "정책 결정",
        "정책 시행",
        "정책 개편",
        "대책 발표",
        "추가 인상",
        "인상",
        "인하",
        "동결",
        "유지",
        "공고",
        "요구",
        "촉구",
        "줄여라",
    ),
    "EARNINGS": ("실적", "매출", "영업이익", "순이익", "가이던스", "공시"),
    "AWARD_CHART": ("관왕", "수상", "우승", "기록"),
    "PRODUCT_RELEASE": ("출시", "발매", "선공개", "발표", "공개", "상장", "예약판매", "판매 개시"),
    "INDUSTRY_CHANGE": (
        "투자",
        "유치",
        "인수",
        "서비스 전환",
        "할당",
        "계약",
        "생산",
        "확대",
        "축소",
    ),
    "SPORTS_INTERRUPTION": ("중단", "멈춘", "휴식", "재개", "취소"),
    "SPORTS_RESULT": (
        "경기 결과",
        "승리",
        "패배",
        "우승",
        "선정",
        "승률",
        "연승",
        "연패",
        "홈런",
        "순위",
        "기록",
    ),
    "SPORTS_ATTENDANCE": ("돌파", "기록", "증가", "감소", "매진"),
    "ROSTER_PERSONNEL": ("선발", "엔트리", "부상", "트레이드", "등록", "말소"),
    "RECRUITMENT_COMPETITION": ("경쟁률", "지원", "지원자", "선발"),
    "RECRUITMENT_RESULT": ("합격", "선발", "발표"),
    "RECRUITMENT_SCHEDULE": ("일정", "시험일", "원서접수", "공고", "접수"),
    "RECRUITMENT_APPLICATION": ("채용", "공채", "모집", "지원"),
    "SCHEDULED_EVENT": ("일정", "예정", "개최", "시구", "공연", "콘서트", "컴백", "월드투어"),
    "ANNOUNCEMENT": ("발표", "공지", "공개"),
    "STATISTIC": ("통계", "지표", "평균", "변동폭", "최고", "최대", "최저", "상승", "하락", "증가", "감소"),
    "MARKET": (*_MARKET_DIRECTION_TERMS, "환율", "코스피", "코스닥", "증시", "주가", "금리"),
    "MARKET_MOVE": (*_MARKET_DIRECTION_TERMS, "환율", "코스피", "코스닥", "증시", "주가", "금리"),
}

_INDUSTRY_MATERIAL_ACTIONS = (
    "투자",
    "유치",
    "인수",
    "서비스 전환",
    "할당",
    "계약",
    "확대",
    "축소",
    "증가",
    "감소",
)
_INDUSTRY_TREND_RE = re.compile(
    r"^(?P<domain>[A-Za-z0-9가-힣·& ]{2,28}?)(?:에|에서)\s+"
    r"(?:부는|번지는|퍼지는|확산하는)\s+"
    r"(?P<object>[A-Za-z0-9가-힣·&'’\- ]{2,32}?)\s+"
    r"(?:붐|열풍|유행)(?:[,，]|$)"
)
_ROSTER_SELECTION_PREDICATE_RE = re.compile(
    r"(?:선발(?:\s*투수)?(?:로|은|이|을)?\s*"
    r"(?:[^.!?]{0,24})?(?:예고|확정|발탁|지명|등록|선정|됐다|되었다|한다|예정)|"
    r"(?:예고|확정|발탁|지명|등록|선정)[^.!?]{0,16}선발)"
)
_RELATION_SUBJECT = r"[A-Za-z0-9가-힣·&'’\- ]{2,56}?"
_RELATION_OBJECT = r"[A-Za-z0-9가-힣·&'’\-–—%., ]{2,96}?"
_RELATION_ACTOR_BOUNDARY = r"(?:(?:은|는|이|가|에서)\s+|[,，]\s*)"
_REGULATION_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT}){_RELATION_ACTOR_BOUNDARY}"
    rf"(?P<object>{_RELATION_OBJECT}(?:규제|법안|법률|고시|제도))(?:을|를)?\s*"
    r"(?P<action>완화|폐지|강화|개정|시행|허용|금지|해제|확정|푼다|"
    r"풀(?:기로(?:\s+확정)?|었다|었다|어|고|기로)?)(?:했다|한다|됐다|된다|하기로\s+했다|키로\s+했다)?$",
    re.IGNORECASE,
)
_INDUSTRY_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT}){_RELATION_ACTOR_BOUNDARY}"
    rf"(?P<object>{_RELATION_OBJECT})\s+"
    r"(?P<action>착공식|착공|공급|수주|신설|출범|투자|지원)"
    r"(?:을|를|에)?\s*(?:했다|한다|됐다|된다|하기로\s+했다|키로\s+했다|"
    r"예정이다|나섰다|시작했다|연다|열었다|들어갔다|확정했다)?$",
    re.IGNORECASE,
)
_SELECTION_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT}){_RELATION_ACTOR_BOUNDARY}"
    rf"(?P<object>{_RELATION_OBJECT}(?:프로그램|파트너|협력사|참여사|대상|기업|회사|Program|Partner))"
    r"(?:에|로|으로|을|를)?\s*(?P<action>선정|지정)"
    r"(?:됐다|되었다|했다|한다|확정됐다)?$",
    re.IGNORECASE,
)
_CONTRACT_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT})(?:(?:은|는|이|가)\s+|[,，]\s*)"
    rf"(?P<object>{_RELATION_OBJECT}(?:전속\s*계약|계약))(?:을|를)?\s*"
    r"(?P<action>해지|종료|만료|해제)(?:했다|한다|됐다|된다|하기로\s+했다)?$",
    re.IGNORECASE,
)
_AFFILIATION_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT})(?:(?:도|은|는|이|가)\s+|[,，]\s*)"
    rf"(?P<object>{_RELATION_OBJECT}(?:JYP|YG|SM|HYBE|하이브|소속사|기획사))(?:를|을)?\s*"
    r"(?P<action>떠난다|떠났다|결별|이적)(?:했다|한다|됐다|된다)?$",
    re.IGNORECASE,
)
_ROSTER_OUTCOME_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT})(?:(?:은|는|이|가)\s+|[,，]\s*)"
    rf"(?P<object>{_RELATION_OBJECT})\s+"
    r"(?P<action>영입\s*무산|영입\s*확정|계약\s*체결|방출|이적\s*확정|트레이드\s*성사)"
    r"(?:됐다|되었다|했다|한다)?$",
    re.IGNORECASE,
)
_ENGLISH_CHART_RELATION_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?P<action>ranks?|ranked|debuts?|debuted|enters?|entered|"
    r"stays?|stayed|remains?|remained|lands?|landed|reaches?|reached)\s+"
    r"(?P<object>.+?\b(?:billboard|chart|charts)\b.+)$",
    re.IGNORECASE,
)
_ENGLISH_CHART_RANK_RE = re.compile(
    r"(?:\bno\.?\s*|#)(\d+)|\b(\d+)(?:st|nd|rd|th)\s+(?:place|position)\b",
    re.IGNORECASE,
)
_ENGLISH_CHART_STREAK_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\s+week\b", re.IGNORECASE)
_ENGLISH_EXECUTIVE_ROLE = (
    r"(?:chief\s+(?:executive|financial|operating|technology|revenue|product|legal|"
    r"marketing|commercial|strategy)\s+officer|CEO|CFO|COO|CTO|CRO|CPO|CLO|CMO|"
    r"president|chair(?:man|woman|person)?|general\s+counsel)"
)
_ENGLISH_CORPORATE_REPLACEMENT_RE = re.compile(
    rf"^(?P<subject>[A-Za-z0-9][A-Za-z0-9&.'’\- ]{{1,79}}?)\s+"
    rf"(?P<action>replaces?|replaced)\s+(?:its\s+|the\s+)?"
    rf"(?P<object>{_ENGLISH_EXECUTIVE_ROLE})"
    r"(?:\s+(?:after|following|amid)\b.*)?$",
    re.IGNORECASE,
)
_ENGLISH_CORPORATE_REPLACEMENT_UNSAFE_RE = re.compile(
    r"\b(?:may|might|could|would|will|reportedly|allegedly|rumou?red|"
    r"plans?\s+to|seeks?\s+to|aims?\s+to|expected\s+to)\s+replac(?:e|es|ed)\b",
    re.IGNORECASE,
)
_INDUSTRY_BARE_RELATION_RE = re.compile(
    rf"^(?P<subject>[A-Za-z0-9가-힣·&'’\-]{{2,40}})\s+"
    rf"(?P<object>{_RELATION_OBJECT})\s+"
    r"(?P<action>착공식|착공|공급|수주|신설|출범|투자|지원)"
    r"(?:을|를|에)?\s*(?:했다|한다|됐다|된다|하기로\s+했다|키로\s+했다|"
    r"예정이다|나섰다|시작했다|연다|열었다|들어갔다|확정했다)?$",
    re.IGNORECASE,
)
_AFFILIATION_BARE_RELATION_RE = re.compile(
    rf"^(?P<subject>{_RELATION_SUBJECT})\s+"
    r"(?P<object>(?:\d+\s*년\s*만에\s+)?(?:JYP|YG|SM|HYBE|하이브|소속사|기획사))"
    r"(?:를|을)?\s*(?P<action>떠난다|떠났다|결별|이적)(?:했다|한다|됐다|된다)?$",
    re.IGNORECASE,
)
_ROSTER_CAUSE_OUTCOME_RELATION_RE = re.compile(
    r"^(?:KBO\s+)?(?:규정\s+착오|행정\s+착오|절차\s+문제)(?:로|때문에)\s+"
    rf"(?P<subject>{_RELATION_SUBJECT})\s+"
    rf"(?P<object>{_RELATION_OBJECT})\s+"
    r"(?P<action>영입\s*무산|영입\s*확정|계약\s*체결|방출|이적\s*확정|트레이드\s*성사)"
    r"(?:됐다|되었다|했다|한다)?$",
    re.IGNORECASE,
)
_UNCLASSIFIED_EVENT_SIGNAL_RE = re.compile(
    r"(?:\b(?:replaces?|replaced|appoints?|appointed|acquires?|acquired)\b|"
    r"(?:편입|편출|교체|선임|임명|공급|수주|신설|출범|인수)"
    r"(?:했다|됐다|한다|된다)?(?=$|[\s,，:;])|"
    r"영입\s*무산|계약\s*체결|떠난다|떠났다)",
    re.IGNORECASE,
)
_UNCLASSIFIED_EVENT_UNSAFE_RE = re.compile(
    r"(?:가능성|전망|거론|검토|논의|분석|설명|주장|rumou?red|reportedly|"
    r"\bmay\b|\bmight\b|\bcould\b|\bwould\b|\bwill\b|\bplans?\s+to\b)",
    re.IGNORECASE,
)

_RELATION_NON_EVENT_TAIL_RE = re.compile(
    r"(?:필요성|가능성|전망|거론|제기|검토|논의|분석|설명|주장|촉구|요구)(?:을|를|이|가|은|는)?\s*"
    r"(?:제기|거론|설명|전망|주장|촉구|요구)?(?:했다|한다|됐다|된다)?$"
)
_INDUSTRY_RELATION_OBJECT_MARKERS: dict[str, tuple[str, ...]] = {
    "착공": ("공장", "센터", "시설", "단지", "라인", "캠퍼스", "기지"),
    "공급": ("솔루션", "서비스", "제품", "장비", "시스템", "반도체", "계약", "부처", "기관"),
    "수주": ("공장", "계약", "사업", "프로젝트", "달러", "원"),
    "신설": ("사업단", "센터", "조직", "법인", "부서", "본부"),
    "출범": ("스타트업", "법인", "회사", "사업", "서비스", "센터"),
    "투자": ("금", "반도체", "공장", "사업", "설비", "기술", "달러", "원"),
    "지원": ("투자", "착공", "이행", "사업", "규제", "공장"),
}
_FOCUS_STOPWORDS = frozenset(
    {
        "관련",
        "소식",
        "기사",
        "보도",
        "주요",
        "원전",
        "온다",
        "부는",
        "붐",
        "열풍",
        "유행",
        "변화",
        "전략",
    }
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


def roster_selection_action_supported(text: str) -> bool:
    """Require an explicit personnel predicate, not the role noun 선발."""

    return bool(_ROSTER_SELECTION_PREDICATE_RE.search(normalize_text(text)))


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


@dataclass(frozen=True)
class EventFact:
    """A typed, source-backed fact that belongs to one canonical event.

    ``role`` is deliberately small and event-family specific (for example
    ``APPLICANT_COUNT`` or ``CHART_RANK``).  Downstream stages consume these
    facts instead of splitting numbers out of prose and trying to bind them
    again.
    """

    role: str
    value: str
    unit: str = ""
    subject: str = ""
    related_value: str = ""
    related_subject: str = ""
    relation: str = ""
    object: str = ""
    evidence_owner_ids: tuple[str, ...] = ()
    canonical_event_id: str = ""


def _relation_subject(value: str) -> str:
    subject = normalize_text(value).strip(" ,·-—")
    subject = re.sub(r"^(?:규정\s+착오|행정\s+착오|절차\s+문제)(?:로|때문에)\s+", "", subject)
    subject = re.sub(r"(?:\d+\s*년\s*만에|\d+\s*일\s*만에)\s*", "", subject)
    subject = re.sub(r"(?:은|는|이|가|도|에서)$", "", subject).strip(" ,·-—")
    if re.search(r"[,，]", subject):
        subject = re.split(r"[,，]", subject)[-1].strip(" ,·-—")
    return subject[:56]


def _relation_object(value: str, *, strip_elapsed: bool = False) -> str:
    object_text = re.sub(
        r"(?:은|는|이|가|을|를|에|로|으로)$",
        "",
        normalize_text(value).strip(" ,·-—"),
    ).strip(" ,·-—")
    if strip_elapsed:
        object_text = re.sub(r"^(?:\d+\s*년\s*만에|\d+\s*일\s*만에)\s+", "", object_text)
    return object_text[:96]


def _relation_fact(
    event_type: str,
    match: re.Match[str],
    action: str,
    *,
    strip_elapsed_object: bool = False,
) -> tuple[str, EventFact] | None:
    subject = _relation_subject(match.group("subject"))
    object_text = _relation_object(match.group("object"), strip_elapsed=strip_elapsed_object)
    if len(compact(subject)) < 2 or len(compact(object_text)) < 2:
        return None
    return (
        event_type,
        EventFact(
            "EVENT_RELATION",
            object_text,
            subject=subject,
            relation=action,
            object=object_text,
        ),
    )


def typed_event_relation(text: str) -> tuple[str, EventFact] | None:
    """Return one explicit subject-predicate-object relation from a headline.

    The matcher is deliberately narrower than an action vocabulary.  A word
    such as ``전략`` or ``선정`` is never sufficient by itself: the headline
    must bind an actor, a compatible material object, and a completed or
    headline-nominal predicate.  This relation is reused by classification,
    ownership, synthesis, and recall diagnostics.
    """

    clean = normalize_text(text).strip(" .!?。！？")
    if not clean or _RELATION_NON_EVENT_TAIL_RE.search(clean):
        return None

    if not _ENGLISH_CORPORATE_REPLACEMENT_UNSAFE_RE.search(clean):
        corporate_replacement = _ENGLISH_CORPORATE_REPLACEMENT_RE.match(clean)
        if corporate_replacement is not None:
            return _relation_fact("ANNOUNCEMENT", corporate_replacement, "교체")

    regulation = _REGULATION_RELATION_RE.match(clean)
    if regulation is not None:
        raw_action = regulation.group("action")
        action = "완화" if raw_action.startswith(("풀", "푼", "해제")) else re.match(
            r"완화|폐지|강화|개정|시행|허용|금지|확정",
            raw_action,
        ).group(0)
        return _relation_fact("REGULATION", regulation, action)

    selection = _SELECTION_RELATION_RE.match(clean)
    if selection is not None:
        return _relation_fact("ANNOUNCEMENT", selection, selection.group("action")[:2])

    contract = _CONTRACT_RELATION_RE.match(clean)
    if contract is not None:
        return _relation_fact("ANNOUNCEMENT", contract, contract.group("action")[:2])

    affiliation = _AFFILIATION_RELATION_RE.match(clean) or _AFFILIATION_BARE_RELATION_RE.match(clean)
    if affiliation is not None:
        raw_action = affiliation.group("action")
        action = "떠남" if raw_action.startswith("떠") else "결별" if raw_action.startswith("결별") else "이적"
        return _relation_fact(
            "ANNOUNCEMENT",
            affiliation,
            action,
            strip_elapsed_object=True,
        )

    roster = _ROSTER_OUTCOME_RELATION_RE.match(clean) or _ROSTER_CAUSE_OUTCOME_RELATION_RE.match(clean)
    if roster is not None:
        return _relation_fact("ROSTER_PERSONNEL", roster, normalize_text(roster.group("action")))

    industry = _INDUSTRY_RELATION_RE.match(clean) or _INDUSTRY_BARE_RELATION_RE.match(clean)
    if industry is not None:
        raw_action = industry.group("action")
        action = "착공" if raw_action.startswith("착공") else raw_action
        object_text = normalize_text(industry.group("object"))
        compatible = _INDUSTRY_RELATION_OBJECT_MARKERS.get(action, ())
        if compatible and not any(marker.casefold() in object_text.casefold() for marker in compatible):
            return None
        return _relation_fact("INDUSTRY_CHANGE", industry, action)

    chart = _ENGLISH_CHART_RELATION_RE.match(clean)
    if chart is not None and (
        _ENGLISH_CHART_RANK_RE.search(clean) or _ENGLISH_CHART_STREAK_RE.search(clean)
    ):
        return _relation_fact("AWARD_CHART", chart, "순위 기록")
    return None


def explicit_unclassified_event_signal(text: str) -> bool:
    """Return a review-only signal for a concrete-looking unclassified event.

    This helper never selects a story. It only prevents a zero-story run from
    being declared safely empty when a directly phrased event predicate fell
    outside the canonical parser. Uncertainty and question forms fail closed.
    """

    clean = normalize_text(text).strip(" .!?。！？")
    if not clean or text.rstrip().endswith(("?", "？")):
        return False
    if typed_event_relation(clean) is not None:
        return False
    if _RELATION_NON_EVENT_TAIL_RE.search(clean) or _UNCLASSIFIED_EVENT_UNSAFE_RE.search(clean):
        return False
    return bool(_UNCLASSIFIED_EVENT_SIGNAL_RE.search(clean))


@dataclass(frozen=True)
class CanonicalEvent:
    """One bounded semantic representation shared by editorial stages."""

    event_type: str
    subject: str = ""
    action: str = ""
    actor: str = ""
    object: str = ""
    condition: str = ""
    date: str = ""
    period: str = ""
    metric: str = ""
    value: str = ""
    direction: str = ""
    unit: str = ""
    observations: tuple[MetricObservation, ...] = ()
    facts: tuple[EventFact, ...] = ()
    evidence_detail: str = ""
    location: str = ""
    temporal_state: str = ""
    temporal_facts: tuple[TemporalFact, ...] = ()
    cause: str = ""
    fixture_id: str = ""
    canonical_event_id: str = ""
    fact_complete: bool = False
    needs_enrichment: bool = False
    event_signature: str = ""
    conflict_state: str = "NO_CONFLICT"
    evidence_owner_ids: tuple[str, ...] = ()
    representative_evidence_id: str = ""
    primary_focus_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyRoles:
    """Bounded roles for a policy statement.

    The parser intentionally handles only explicit institutional statements.
    Unknown roles stay empty instead of promoting a condition or policy noun
    into the actor/action slots.
    """

    actor: str = ""
    condition: str = ""
    object: str = ""
    action: str = ""


def _focus_token(value: str) -> str:
    token = normalize_text(value).strip(" ,:·-—()[]{}\"'“”‘’")
    for suffix in (
        "에서는",
        "에게서",
        "으로",
        "에서",
        "에게",
        "까지",
        "부터",
        "에",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "의",
    ):
        if len(compact(token)) >= len(compact(suffix)) + 2 and token.endswith(suffix):
            token = token[: -len(suffix)].strip()
            break
    return token


def primary_event_focus_terms(
    event_type: str,
    title: str,
    subject: str,
    facts: tuple[EventFact, ...] = (),
) -> tuple[str, ...]:
    """Return bounded terms that identify the story's primary event focus.

    Evidence ownership is source-level. These terms add the smaller guard
    needed when one owned article contains a headline event plus unrelated
    examples or background events in its lead.
    """

    candidates: list[str] = []
    for fact in facts:
        if fact.role == "TREND_CHANGE":
            candidates.extend((fact.subject, fact.value, fact.object))
    candidates.extend(re.findall(r"[A-Za-z0-9가-힣·&'’\-]+", subject))
    if not candidates:
        candidates.extend(re.findall(r"[A-Za-z0-9가-힣·&'’\-]+", title)[:3])
    terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        token = _focus_token(candidate)
        folded = compact(token)
        if len(folded) < 2 or folded in _FOCUS_STOPWORDS or folded in seen:
            continue
        seen.add(folded)
        terms.append(token)
    return tuple(terms[:5])


def summary_preserves_primary_focus(
    summary: str,
    focus_terms: tuple[str, ...],
) -> bool:
    """Reject a summary that silently switches to a secondary sub-event."""

    if not focus_terms:
        return True
    summary_key = compact(summary)
    return any(compact(term) and compact(term) in summary_key for term in focus_terms)


_POLICY_OBJECT_RE = re.compile(r"(?<![가-힣A-Za-z0-9])(?:기준금리|정책금리)(?![가-힣A-Za-z0-9])")
_POLICY_CONDITION_RE = re.compile(
    r"(?P<condition>[A-Za-z0-9가-힣· ]{2,36}?)\s*"
    r"(?P<ending>없다면|없으면|없을\s+경우|없는\s+경우|있다면|있으면|있을\s+경우)$"
)
_POLICY_ACTOR_RE = re.compile(
    r"(?:^|(?<=[.!?。！？])\s)"
    r"(?P<actor>[A-Za-z가-힣· ]{2,48}?(?:부총재|총재|장관|위원장|위원|대통령))"
    r"(?:은|는|이|가)\s+"
)


def _strip_policy_particle(value: str) -> str:
    return re.sub(r"(?:은|는|이|가|을|를)$", "", normalize_text(value)).strip(" ,·-—")


def _policy_action(value: str) -> str:
    text = fold(value)
    possibility = any(marker in text for marker in ("가능성", "가능", "시사", "언급", "말했다"))
    if "인상" in text or "올릴" in text or "올리" in text:
        prefix = "추가 " if "추가" in text else ""
        return f"{prefix}인상 가능성 언급" if possibility else f"{prefix}인상".strip()
    if "인하" in text or "내릴" in text or "내리" in text:
        return "인하 가능성 언급" if possibility else "인하"
    if "동결" in text:
        return "동결"
    if "유지" in text:
        return "유지"
    if "발표" in text:
        return "발표"
    if "결정" in text:
        return "결정"
    return ""


def policy_roles(title: str, lead: str = "") -> PolicyRoles:
    """Extract actor/condition/object/action without crossing their roles."""

    title_text = normalize_text(title)
    lead_text = normalize_text(lead)
    object_match = _POLICY_OBJECT_RE.search(title_text) or _POLICY_OBJECT_RE.search(lead_text)
    if object_match is None:
        return PolicyRoles()

    object_text = object_match.group(0)
    title_object = _POLICY_OBJECT_RE.search(title_text)
    actor = ""
    condition = ""
    action_evidence = ""
    if title_object is not None:
        prefix = title_text[: title_object.start()].strip(" ,·-—")
        condition_match = _POLICY_CONDITION_RE.search(prefix)
        if condition_match is not None:
            condition = normalize_text(condition_match.group(0))
            role_split = re.match(
                r"^(?P<actor>.*(?:부총재|총재|장관|위원장|위원|대통령|정부|한국은행|한은))"
                r"\s+(?P<condition>.+)$",
                condition,
            )
            if role_split is not None:
                actor = _strip_policy_particle(role_split.group("actor"))
                condition = normalize_text(role_split.group("condition"))
            else:
                actor = _strip_policy_particle(prefix[: condition_match.start()])
        else:
            actor = _strip_policy_particle(prefix)
        actor = re.sub(
            r"[,，]?\s*(?:20\d{2}\s*년\s*)?\d{1,2}\s*월\s*\d{1,2}\s*일$",
            "",
            actor,
        ).strip(" ,·-—")
        action_evidence = title_text[title_object.end() :]

    lead_actor = _POLICY_ACTOR_RE.search(lead_text)
    if lead_actor is not None:
        actor = _strip_policy_particle(lead_actor.group("actor"))
    lead_object = _POLICY_OBJECT_RE.search(lead_text)
    if lead_object is not None:
        action_evidence = f"{action_evidence} {lead_text[lead_object.end():]}".strip()

    return PolicyRoles(
        actor=actor,
        condition=condition,
        object=object_text,
        action=_policy_action(action_evidence),
    )


_RECRUITMENT_SELECTED_RE = re.compile(
    r"(?<!\d)(\d[\d,]*)\s*명\s*(?:을|를|이|가)?\s*(?:선발|모집)"
)
_RECRUITMENT_SELECTED_REVERSED_RE = re.compile(
    r"(?:선발|모집)(?:하는|할|한|은|는|이|가|을|를)?\s*(?<!\d)(\d[\d,]*)\s*명"
)
_RECRUITMENT_APPLICANT_RE = re.compile(
    r"(?<!\d)(\d[\d,]*)\s*명\s*(?:이|가|은|는|을|를)?\s*(?:지원|응시)"
)
_VOTE_RE = re.compile(r"(?<!\d)(\d[\d,]*)\s*표")
_RANK_RE = re.compile(r"(?<!\d)(\d+)\s*위")
_STREAK_RE = re.compile(r"(?<!\d)(\d+)\s*주\s*연속")
_HOME_RUN_RE = re.compile(r"(?<!\d)(\d+)\s*홈런")
_RBI_RE = re.compile(r"(?<!\d)(\d+)\s*타점")
_GAME_SCORE_RE = re.compile(r"(?<!\d)(\d+)\s*[-:]\s*(\d+)(?!\d)")
_LOCATION_RE = re.compile(
    r"(?<![A-Za-z가-힣])(?:서울|부산|광주|대전|인천|제주|판교|여의도|뉴욕|도쿄|싱가포르|충칭|DDP)(?![A-Za-z가-힣])"
)
_SPORTS_TEAM_NAMES = (
    "한화",
    "두산",
    "LG",
    "KT",
    "SSG",
    "KIA",
    "롯데",
    "삼성",
    "NC",
    "키움",
)


def _normalized_number(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def _fact(role: str, value: str, *, unit: str = "", subject: str = "") -> EventFact:
    return EventFact(role, _normalized_number(value), unit, normalize_text(subject))


_INDUSTRY_VALUE_PATTERN = (
    r"[+-]?\d[\d,.]*"
    r"(?:\s?(?:조원|억원|만원|천만원|천만|만\s?달러|억\s?달러|달러|"
    r"백만대|천대|만대|MW|GW|%|퍼센트|만|천|백만|원|대|건|개|명|배))?"
)
_INDUSTRY_VALUE_RE = re.compile(
    rf"(?<![{_WORD_CHAR}])(?P<value>{_INDUSTRY_VALUE_PATTERN})"
    r"(?=$|[\s,，.·:;!?]|(?:에|의|을|를|은|는|이|가|로|에서|까지))",
    re.IGNORECASE,
)
_INDUSTRY_PAIR_RE = re.compile(
    rf"(?P<left>{_INDUSTRY_VALUE_PATTERN})\s*"
    r"(?P<relation>vs|VS|대비|→|->|에서)\s*"
    r"(?:(?P<right_subject>[A-Za-z가-힣][A-Za-z가-힣A-Za-z0-9· ]{0,20}?)\s+)?"
    rf"(?P<right>{_INDUSTRY_VALUE_PATTERN})\s*(?:로|까지)?",
    re.IGNORECASE,
)
_INDUSTRY_ACTIONS = (
    "투자",
    "유치",
    "인수",
    "계약",
    "공급",
    "생산",
    "전략",
    "할당",
    "고도화",
    "확대",
    "축소",
)
_INDUSTRY_AMOUNT_UNITS = ("조원", "억원", "만원", "천만원", "달러", "원")
_INDUSTRY_QUANTITY_UNITS = ("백만대", "천대", "만대", "대", "건", "개", "명")


def _industry_value(value: str) -> str:
    return _normalized_number(value)


def _industry_is_date(value: str) -> bool:
    compact_value = _industry_value(value)
    return bool(re.fullmatch(r"(?:20\d{2})?(?:년|월|일)", compact_value))


def _industry_has_unit(value: str, units: tuple[str, ...]) -> bool:
    compact_value = _industry_value(value)
    return any(compact_value.endswith(unit) for unit in units)


def _industry_context(text: str, start: int, end: int, radius: int = 28) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def industry_change_facts(text: str) -> tuple[EventFact, ...]:
    """Extract bounded fact relationships for an ``INDUSTRY_CHANGE`` event.

    The parser intentionally recognizes only source-explicit relationships.
    A bare number, a publication date, or two unrelated metrics is not
    promoted to an industry fact.  Paired values remain one fact so synthesis
    cannot bind one entity's number to another entity or discard the relation.
    """

    clean = normalize_text(text)
    if not clean:
        return ()
    facts: list[EventFact] = []
    occupied: list[tuple[int, int]] = []

    for match in _INDUSTRY_PAIR_RE.finditer(clean):
        left = _industry_value(match.group("left"))
        right = _industry_value(match.group("right"))
        if not left or not right or _industry_is_date(left) or _industry_is_date(right):
            continue
        context = _industry_context(clean, match.start(), match.end())
        relation = match.group("relation").casefold()
        if "%" in left or "%" in right or "퍼센트" in left or "퍼센트" in right or any(
            marker in context for marker in ("점유율", "비중", "비율", "경쟁률")
        ):
            role = "RATIO_CHANGE"
            unit = "PERCENT" if ("%" in left or "퍼센트" in left or "%" in right or "퍼센트" in right) else "RATIO"
        elif any(marker.casefold() in context.casefold() for marker in ("생산", "생산량", "용량", "capacity", "가동", "처리량")):
            role = "PRODUCTION_CHANGE"
            unit = "QUANTITY"
        else:
            role = "COMPARISON"
            unit = "VALUE"
        facts.append(
            EventFact(
                role,
                left,
                unit=unit,
                related_value=right,
                related_subject=normalize_text(match.group("right_subject") or "").strip(),
                relation="CHANGE" if relation == "에서" else relation.upper(),
            )
        )
        occupied.append(match.span())

    for match in _INDUSTRY_VALUE_RE.finditer(clean):
        if _span_overlaps(match.span(), occupied):
            continue
        value = _industry_value(match.group("value"))
        if not value or _industry_is_date(value):
            continue
        context = _industry_context(clean, match.start(), match.end())
        actions = tuple(
            marker
            for marker in _INDUSTRY_ACTIONS
            if contains_boundary_term(context, marker) or marker in context
        )
        if not actions:
            continue
        if _industry_has_unit(value, _INDUSTRY_AMOUNT_UNITS):
            if any(marker in context for marker in ("인수",)):
                role = "ACQUISITION_AMOUNT"
            elif any(marker in context for marker in ("투자", "유치", "출자")):
                role = "INVESTMENT_AMOUNT"
            elif any(marker in context for marker in ("전략", "고도화", "확대", "축소")):
                role = "STRATEGY_AMOUNT"
            else:
                continue
            facts.append(EventFact(role, value, unit="AMOUNT"))
            occupied.append(match.span())
            continue
        if _industry_has_unit(value, _INDUSTRY_QUANTITY_UNITS):
            if any(marker in context for marker in ("계약", "공급")):
                role = "CONTRACT_QUANTITY"
            elif any(marker in context for marker in ("생산", "생산량", "용량", "capacity")):
                role = "PRODUCTION_QUANTITY"
            else:
                continue
            facts.append(EventFact(role, value, unit="QUANTITY"))
            occupied.append(match.span())

    # Preserve insertion order while keeping a repeated value from creating
    # multiple independent facts in downstream summaries.
    return tuple(dict.fromkeys(facts))


def industry_trend_fact(title: str) -> EventFact | None:
    """Represent an explicitly framed multi-entity trend as one event fact.

    This is deliberately narrower than treating words such as ``전략`` or
    ``트렌드`` as actions. The headline itself must bind a domain, a trend
    object, and an explicit spread/boom marker.
    """

    match = _INDUSTRY_TREND_RE.search(normalize_text(title))
    if match is None:
        return None
    domain = match.group("domain").strip(" ,·-—")
    trend_object = match.group("object").strip(" ,·-—")
    if not domain or not trend_object:
        return None
    return EventFact(
        "TREND_CHANGE",
        trend_object,
        subject=domain,
        relation="확산",
        object=trend_object,
    )


def recruitment_facts(text: str) -> tuple[EventFact, ...]:
    """Extract recruitment counts without confusing them with sports roster facts."""

    clean = normalize_text(text)
    facts: list[EventFact] = []
    ratio = _RECRUITMENT_RATIO_RE.search(clean)
    if ratio:
        facts.append(_fact("COMPETITION_RATIO", ratio.group(0), unit="RATIO"))
    selected = _RECRUITMENT_SELECTED_RE.search(clean) or _RECRUITMENT_SELECTED_REVERSED_RE.search(clean)
    if selected:
        facts.append(_fact("SELECTION_COUNT", selected.group(1), unit="명"))
    applicants = _RECRUITMENT_APPLICANT_RE.search(clean)
    if applicants:
        facts.append(_fact("APPLICANT_COUNT", applicants.group(1), unit="명"))
    return tuple(dict.fromkeys(facts))


def award_chart_facts(text: str) -> tuple[EventFact, ...]:
    """Return bound chart/award facts; fan popularity polls remain identifiable."""

    clean = normalize_text(text)
    facts: list[EventFact] = []
    rank = _RANK_RE.search(clean)
    if rank:
        facts.append(_fact("CHART_RANK", rank.group(1), unit="위"))
    else:
        english_rank = _ENGLISH_CHART_RANK_RE.search(clean)
        if english_rank:
            facts.append(_fact("CHART_RANK", next(value for value in english_rank.groups() if value), unit="위"))
    streak = _STREAK_RE.search(clean)
    if streak:
        facts.append(_fact("STREAK_WEEKS", streak.group(1), unit="주"))
    else:
        english_streak = _ENGLISH_CHART_STREAK_RE.search(clean)
        if english_streak:
            facts.append(_fact("STREAK_WEEKS", english_streak.group(1), unit="주"))
    votes = _VOTE_RE.search(clean)
    if votes:
        facts.append(_fact("VOTE_COUNT", votes.group(1), unit="표"))
    return tuple(facts)


def sports_result_facts(text: str) -> tuple[EventFact, ...]:
    """Bind a result/award and its performance numbers to one sports event."""

    clean = normalize_text(text)
    facts: list[EventFact] = []
    if re.search(r"(?<![A-Za-z])MVP(?![A-Za-z])", clean, re.IGNORECASE):
        facts.append(_fact("AWARD", "MVP"))
    score = _GAME_SCORE_RE.search(clean)
    if score:
        facts.append(_fact("GAME_SCORE", f"{score.group(1)}-{score.group(2)}", unit="SCORE"))
    home_runs = _HOME_RUN_RE.search(clean)
    if home_runs:
        facts.append(_fact("HOME_RUN_COUNT", home_runs.group(1), unit="홈런"))
    rbi = _RBI_RE.search(clean)
    if rbi:
        facts.append(_fact("RBI_COUNT", rbi.group(1), unit="타점"))
    period = _PERIOD_RE.search(clean)
    if period:
        facts.append(_fact("PERIOD", period.group(0).replace(" ", "")))
    return tuple(facts)


def is_low_value_popularity_poll(text: str) -> bool:
    """Identify fan-vote popularity content, not recognized music-chart results."""

    value = fold(text)
    return any(
        compact(marker) in compact(value)
        for marker in ("인기투표", "팬 투표", "팬투표", "평점랭킹", "선호도 투표")
    )


def _lead_subject(lead: str) -> str:
    """Extract only a sentence-leading, explicitly particle-bound subject."""

    match = re.match(
        r"^([A-Za-z0-9가-힣·&'’\- ]{2,48}?)(?:이|가|은|는)\s+(?=\S)",
        normalize_text(lead).strip(),
    )
    if not match:
        return ""
    candidate = match.group(1).strip(" ,·-—")
    candidate = re.sub(r"[\"'“”‘’]", "", candidate)
    return candidate if candidate and not candidate[0].isdigit() else ""


def _clean_event_subject(event_type: str, value: str) -> str:
    """Keep the actor separate from an audience/object tail in a title."""

    text = re.sub(r"[\"'“”‘’]", "", normalize_text(value)).strip(" ,·-—")
    had_audience_tail = bool(_AUDIENCE_TARGET_RE.search(text))
    text = _AUDIENCE_TARGET_RE.sub("", text).strip(" ,·-—")
    if had_audience_tail and event_type in {"POLICY", "REGULATION"} and re.search(r"[,，]", text):
        text = re.split(r"[,，]", text, maxsplit=1)[0].strip(" ,·-—")
    return text[:64]


def subject_boundary_is_clean(event_type: str, subject: str) -> bool:
    """Reject an audience tail that was accidentally stored as the actor."""

    if event_type not in {"POLICY", "REGULATION"}:
        return True
    return not bool(_AUDIENCE_TARGET_RE.search(normalize_text(subject)))


def _event_subject(
    event_type: str,
    title: str,
    observations: tuple[MetricObservation, ...],
    lead: str = "",
) -> str:
    clean = normalize_text(title).strip(" ,·-—")
    if observations:
        return observations[0].instrument
    if event_type == "EARNINGS":
        return ""
    if event_type == "SPORTS_INTERRUPTION":
        sports_evidence = fold(f"{clean} {lead}")
        return (
            "프로야구"
            if any(term in sports_evidence for term in ("프로야구", "kbo", "야구"))
            else ""
        )
    if event_type == "SPORTS_RESULT":
        # Performance headlines often put the numbers before the player.
        # A metadata lead with an explicit Korean subject particle is safer
        # than rebuilding an entity from that headline token order.
        return _clean_event_subject(event_type, _lead_subject(lead))
    if event_type.startswith("RECRUITMENT"):
        clean = _RECRUITMENT_RATIO_RE.sub("", clean)
        clean = re.sub(
            r"\s+\d[\d,]*\s*명\s*(?:선발|모집)(?:에|하고|해|,)?(?:.*)$",
            "",
            clean,
        )
        clean = re.sub(r"\s+경쟁률(?:은|이)?\s*$", "", clean)
        return _clean_event_subject(event_type, clean)
    if event_type == "AWARD_CHART":
        english_marker = re.search(
            r"\b(?:ranks?|ranked|debuts?|debuted|enters?|entered|stays?|stayed|"
            r"remains?|remained|lands?|landed|reaches?|reached|billboard|charts?)\b",
            clean,
            re.IGNORECASE,
        )
        if english_marker is not None:
            prefix = clean[: english_marker.start()].strip(" ,·-—'\"")
            tokens = re.findall(r"[A-Za-z0-9가-힣·&'’-]+", prefix)
            return _clean_event_subject(event_type, " ".join(tokens[-4:]))
        prefix = re.split(r"[,，]|\s+(?:국내외\s+)?(?:음악\s+|음원\s+)?차트\b", clean, maxsplit=1)[0]
        prefix = re.sub(r"^(?:\d{1,2}월도\s+)?(?:No\.?\s*\d+\s+)?", "", prefix, flags=re.IGNORECASE)
        tokens = [
            token
            for token in re.findall(r"[A-Za-z0-9가-힣·&'’-]+", prefix)
            if not token.isdigit() and token.casefold() not in {"스타트렌드", "아이돌", "가수", "그룹"}
        ]
        return _clean_event_subject(event_type, " ".join(tokens[-3:]))
    if event_type == "PRODUCT_RELEASE" and re.search(r"[,，]", clean):
        return _clean_event_subject(event_type, re.split(r"[,，]", clean, maxsplit=1)[0])
    if event_type == "INDUSTRY_CHANGE":
        marker = next(
            (
                match
                for term in _EVENT_ACTION_CONTRACTS.get(event_type, ())
                for match in (re.search(rf"(?<![{_WORD_CHAR}]){re.escape(term)}", clean),)
                if match
            ),
            None,
        )
        if marker:
            prefix = clean[: marker.start()].strip(" ,·-—")
            prefix = re.sub(
                r"\s+[+-]?\d[\d,.]*(?:\s?(?:조원|억원|만원|달러|만대|대|건|개|명|%|퍼센트|만|천))?"
                r"(?:에서|으로|로)?\s*$",
                "",
                prefix,
            )
            prefix = re.sub(
                r"\s*[+-]?\d[\d,.]*(?:\s?(?:조원|억원|만원|달러|만대|대|건|개|명|%|퍼센트|만|천))?"
                r"(?:에서|으로|로)?",
                " ",
                prefix,
            )
            prefix = re.sub(r"^[+-]?\d[\d,.]*(?:\s?(?:조원|억원|만원|달러|만대|대|건|개|명|%|퍼센트|만|천))?\s*", "", prefix)
            prefix = re.sub(r"\s+(?:월|주|일|공급|생산량|용량|capacity)\s*$", "", prefix, flags=re.IGNORECASE)
            prefix = re.sub(r"\s+(?:점유율|비중|비율|경쟁률)\s*$", "", prefix)
            prefix = re.sub(r"(?:에서|으로|로|대비)\s*$", "", prefix).strip(" ,·-—")
            prefix = re.sub(r"(?:이|가|은|는)$", "", prefix).strip(" ,·-—")
            if "," in prefix or "，" in prefix:
                prefix = re.split(r"[,，]", prefix, maxsplit=1)[0].strip(" ,·-—")
            if prefix and not re.fullmatch(r"[0-9\s]+", prefix):
                return _clean_event_subject(event_type, prefix)
        lead_subject = _lead_subject(lead)
        if lead_subject and not re.search(r"\d|투자|유치|인수|계약|공급|생산|전략|고도화", lead_subject):
            return _clean_event_subject(event_type, lead_subject)
    # For other families keep only the bounded noun phrase before a clear
    # event predicate.  If no safe boundary exists, leave the title-derived
    # subject to the existing fallback rather than inventing an entity.
    marker = next(
        (
            match
            for term in _EVENT_ACTION_CONTRACTS.get(event_type, ACTION_TERMS)
            for match in (re.search(rf"(?<![{_WORD_CHAR}]){re.escape(term)}", clean),)
            if match
        ),
        None,
    )
    if marker and marker.start() >= 2:
        return _clean_event_subject(event_type, clean[: marker.start()])
    return ""


def sports_interruption_state(event_type: str, text: str) -> tuple[str, str]:
    if event_type != "SPORTS_INTERRUPTION":
        return "", ""
    value = fold(text)
    cause = "HEAT" if any(marker in value for marker in ("폭염", "더위", "고온", "열파", "체감")) else (
        "RAIN" if any(marker in value for marker in ("우천", "비로", "폭우")) else ""
    )
    if "재개" in value:
        completed = bool(
            re.search(r"재개(?:됐|되었|했다|된|완료)", value)
            or re.search(r"다시\s+(?:시작됐|시작되었|문을\s+열었)", value)
        )
        if completed:
            return "RESUMED", cause
        future = any(
            marker in value
            for marker in ("예정", "재개한다", "재개할", "재개될", "오늘 재개", "내일", "오는")
        )
        return ("RESUMING" if future else "RESUMED"), cause
    if "취소" in value:
        return "CANCELLED", cause
    if any(marker in value for marker in ("중단", "멈춘", "휴식", "방학")):
        return "INTERRUPTED", cause
    return "", cause


def sports_interruption_title_support(title: str, lead: str = "") -> bool:
    """Require the headline itself to own the lifecycle predicate.

    A lead may supply a cause or a date, but it cannot turn an attendance,
    player, or ceremonial headline into an interruption story merely because
    both mention professional baseball.
    """

    title_text = fold(title)
    combined = fold(f"{title} {lead}")
    sports_context = any(term in combined for term in ("프로야구", "kbo", "한국 야구", "야구"))
    lifecycle_in_title = any(
        marker in title_text
        for marker in (
            "중단",
            "멈춘",
            "멈춰",
            "휴식",
            "방학",
            "취소",
            "재개",
            "재출발",
            "다시 시작",
        )
    )
    return sports_context and lifecycle_in_title


def _span_overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    return any(span[0] < other[1] and other[0] < span[1] for other in occupied)


def _nearest_temporal_role(sentence: str, position: int, event_type: str) -> str:
    markers: list[tuple[int, str]] = []
    if event_type == "SPORTS_INTERRUPTION":
        markers.extend(
            (match.start(), "RESUMPTION_DATE")
            for marker in _RESUMPTION_MARKERS
            for match in re.finditer(re.escape(marker), sentence)
        )
        markers.extend(
            (match.start(), "START_DATE" if marker != "취소" else "EVENT_DATE")
            for marker in _INTERRUPTION_MARKERS
            for match in re.finditer(re.escape(marker), sentence)
        )
    markers.extend(
        (match.start(), "EVENT_DATE")
        for marker in _EVENT_DATE_MARKERS
        for match in re.finditer(re.escape(marker), sentence)
    )
    return min(markers, key=lambda item: abs(item[0] - position))[1] if markers else ""


def temporal_facts(text: str, event_type: str = "") -> tuple[TemporalFact, ...]:
    """Extract time expressions without collapsing duration and calendar roles.

    Relative expressions remain relative unless a publication timestamp is
    available to the caller.  Preserving ``오늘`` is safer than fabricating an
    absolute date and is sufficient for synthesis and lifecycle ordering.
    """

    value = normalize_text(text)
    facts: list[TemporalFact] = []
    for sentence in re.split(r"(?<=[.!?])\s+", value):
        occupied: list[tuple[int, int]] = []
        temporal_patterns = (
            (_DURATION_RE, "DURATION"),
            (_ELAPSED_DURATION_RE, "ELAPSED_DURATION"),
        )
        for pattern, role in temporal_patterns:
            for match in pattern.finditer(sentence):
                raw = match.group(0)
                normalized = re.sub(r"\s+", "", match.group("value"))
                facts.append(TemporalFact(role, normalized, raw))
                occupied.append(match.span())
        for match in _RELATIVE_DATE_RE.finditer(sentence):
            role = _nearest_temporal_role(sentence, match.start(), event_type)
            if role:
                facts.append(TemporalFact(role, match.group(0), match.group(0)))
                occupied.append(match.span())
        for match in _DATE_RE.finditer(sentence):
            if _span_overlaps(match.span(), occupied):
                continue
            role = _nearest_temporal_role(sentence, match.start(), event_type)
            if role:
                facts.append(
                    TemporalFact(role, re.sub(r"\s+", "", match.group(0)), match.group(0))
                )
    return tuple(dict.fromkeys(facts))


def _temporal_values(facts: tuple[TemporalFact, ...], role: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(fact.value for fact in facts if fact.role == role and fact.value))


def _primary_event_date(facts: tuple[TemporalFact, ...], event_type: str, state: str = "") -> str:
    if event_type == "SPORTS_INTERRUPTION" and state in {"RESUMING", "RESUMED"}:
        resumption = _temporal_values(facts, "RESUMPTION_DATE")
        if resumption:
            return resumption[0]
    for role in ("EVENT_DATE", "SCHEDULE_DATE", "START_DATE", "END_DATE"):
        values = _temporal_values(facts, role)
        if values:
            return values[0]
    return ""


def _sports_fixture_id(text: str) -> str:
    value = normalize_text(text)
    teams = tuple(
        dict.fromkeys(
            team
            for team in _SPORTS_TEAM_NAMES
            if re.search(
                rf"(?<![A-Za-z가-힣]){re.escape(team)}(?![A-Za-z가-힣])",
                value,
                re.IGNORECASE,
            )
        )
    )
    return "-".join(sorted(teams, key=str.casefold)) if len(teams) >= 2 else ""


def _sports_lifecycle_id(subject: str, cause: str) -> str:
    return "|".join(part for part in ("SPORTS_INTERRUPTION", compact(subject), cause) if part)


def _sports_event_signature(
    lifecycle_id: str,
    *,
    location: str = "",
    fixture_id: str = "",
    temporal: tuple[TemporalFact, ...] = (),
    state: str = "",
) -> str:
    parts = [lifecycle_id]
    event_date = next(iter(_temporal_values(temporal, "EVENT_DATE")), "")
    if location:
        parts.append(f"LOCATION={compact(location)}")
    if fixture_id:
        parts.append(f"FIXTURE={compact(fixture_id)}")
    if event_date:
        parts.append(f"EVENT_DATE={event_date}")
    if state:
        parts.append(f"STATE={state}")
    return "|".join(part for part in parts if part)


def _signature_lifecycle_parts(signature: str) -> tuple[str, dict[str, str]]:
    parts = tuple(part for part in signature.split("|") if part)
    if not parts or parts[0] != "SPORTS_INTERRUPTION":
        return "", {}
    attributes: dict[str, str] = {}
    base: list[str] = list(parts[:3])
    for part in parts[3:]:
        if "=" in part:
            key, value = part.split("=", 1)
            attributes[key] = value
        elif re.fullmatch(r"\d{1,2}일", part):
            attributes.setdefault("EVENT_DATE", part)
        elif part in {"INTERRUPTED", "CANCELLED", "RESUMING", "RESUMED"}:
            attributes.setdefault("STATE", part)
        else:
            base.append(part)
    return "|".join(base), attributes


def same_lifecycle_signatures(left: str, right: str) -> bool:
    """Compare state-independent lifecycle identity encoded in signatures."""

    if left == right:
        return bool(left)
    left_id, left_attrs = _signature_lifecycle_parts(left)
    right_id, right_attrs = _signature_lifecycle_parts(right)
    if not left_id or left_id != right_id:
        return False
    for field in ("LOCATION", "FIXTURE", "EVENT_DATE"):
        left_value = left_attrs.get(field, "")
        right_value = right_attrs.get(field, "")
        if left_value and right_value and left_value != right_value:
            return False
    return True


def same_event_lifecycle(left: CanonicalEvent, right: CanonicalEvent) -> bool:
    """Return whether two interruption states belong to one bounded event."""

    if left.event_type != "SPORTS_INTERRUPTION" or right.event_type != "SPORTS_INTERRUPTION":
        return left.event_signature == right.event_signature
    return same_lifecycle_signatures(left.event_signature, right.event_signature)


def _event_identity_text(value: str) -> str:
    text = compact(value)
    aliases = (
        ("한국야구위원회", "프로야구"),
        ("kbo", "프로야구"),
        ("한은", "한국은행"),
    )
    for alias, canonical in aliases:
        text = text.replace(alias, canonical)
    return text


def _event_action_family(value: str) -> str:
    text = compact(value)
    for marker in (
        "추가인상",
        "인상",
        "인하",
        "동결",
        "유지",
        "투자",
        "인수",
        "계약",
        "생산",
        "출시",
        "발매",
        "재개",
        "중단",
        "취소",
    ):
        if marker in text:
            return marker.removeprefix("추가")
    return text


def same_canonical_event(left: CanonicalEvent, right: CanonicalEvent) -> bool:
    """Return whether two independently interpreted sources own one event.

    This is deliberately stricter than topic or cluster similarity.  It is
    used only for evidence ownership: conflicting dates, objects, metrics, or
    typed fact values cannot share a final fact pool.
    """

    if left.event_type != right.event_type:
        return False
    if left.event_type == "SPORTS_INTERRUPTION":
        return same_event_lifecycle(left, right)
    if left.canonical_event_id and left.canonical_event_id == right.canonical_event_id:
        return True
    if left.date and right.date and left.date != right.date:
        return False
    if (
        left.object
        and right.object
        and _event_identity_text(left.object) != _event_identity_text(right.object)
    ):
        return False

    left_subject = _event_identity_text(left.actor or left.subject)
    right_subject = _event_identity_text(right.actor or right.subject)
    subject_matches = bool(
        left_subject
        and right_subject
        and (
            left_subject == right_subject
            or left_subject in right_subject
            or right_subject in left_subject
        )
    )
    if left_subject and right_subject and not subject_matches:
        return False

    left_action = _event_action_family(left.action)
    right_action = _event_action_family(right.action)
    action_matches = bool(left_action and right_action and left_action == right_action)
    if left_action and right_action and not action_matches:
        return False

    left_observations = {
        (item.instrument, item.metric, item.period): (item.value, item.direction)
        for item in left.observations
    }
    right_observations = {
        (item.instrument, item.metric, item.period): (item.value, item.direction)
        for item in right.observations
    }
    for key in left_observations.keys() & right_observations.keys():
        if left_observations[key] != right_observations[key]:
            return False

    left_facts = {(fact.role, fact.subject, fact.object): fact.value for fact in left.facts}
    right_facts = {(fact.role, fact.subject, fact.object): fact.value for fact in right.facts}
    fact_overlap = left_facts.keys() & right_facts.keys()
    for key in fact_overlap:
        if left_facts[key] != right_facts[key]:
            return False

    return bool(
        subject_matches
        and (action_matches or fact_overlap or left_observations.keys() & right_observations.keys())
    )


def build_canonical_event(
    event_type: str,
    title: str,
    *,
    lead: str = "",
    action: str = "",
    conflict_state: str = "NO_CONFLICT",
    evidence_owner_ids: tuple[str, ...] = (),
) -> CanonicalEvent:
    """Build the one semantic object consumed by all downstream stages."""

    title_text = normalize_text(title)
    lead_text = normalize_text(lead)
    evidence = " ".join(part for part in (title_text, lead_text) if part)
    typed_relation = typed_event_relation(title_text)
    relation_fact = (
        typed_relation[1]
        if typed_relation is not None and typed_relation[0] == event_type
        else None
    )
    observations = event_observations(event_type, title_text)
    policy = policy_roles(title_text, lead_text) if event_type == "POLICY" else PolicyRoles()
    subject = (relation_fact.subject if relation_fact is not None else "") or policy.actor or _event_subject(
        event_type,
        title_text,
        observations,
        lead_text,
    )
    if event_type == "EARNINGS" and observations:
        event_action = observations[0].direction or "기록"
    else:
        event_action = (relation_fact.relation if relation_fact is not None else "") or policy.action or action or event_action_signal(
            event_type,
            title_text,
            lead_text,
        )
    temporal_state, cause = sports_interruption_state(event_type, evidence)
    if event_type == "SPORTS_INTERRUPTION":
        event_action = {
            "INTERRUPTED": "중단",
            "CANCELLED": "취소",
            "RESUMING": "재개",
            "RESUMED": "재개",
        }.get(temporal_state, event_action)
    temporal = temporal_facts(evidence, event_type)
    date, date_conflict = canonical_event_date(
        title_text,
        lead_text,
        event_type=event_type,
        state=temporal_state,
    )
    facts: tuple[EventFact, ...]
    if event_type.startswith("RECRUITMENT"):
        facts = recruitment_facts(evidence)
    elif event_type == "AWARD_CHART":
        facts = award_chart_facts(evidence)
    elif event_type == "SPORTS_RESULT":
        facts = sports_result_facts(evidence)
    elif event_type == "INDUSTRY_CHANGE":
        trend_fact = industry_trend_fact(title_text)
        material_facts = industry_change_facts(evidence)
        facts = tuple(
            dict.fromkeys(
                (
                    *material_facts,
                    *((trend_fact,) if trend_fact is not None else ()),
                    *((relation_fact,) if relation_fact is not None and not material_facts and trend_fact is None else ()),
                )
            )
        )
        if trend_fact is not None:
            subject = trend_fact.subject
            event_action = trend_fact.relation
    else:
        facts = (relation_fact,) if relation_fact is not None else ()
    location_match = _LOCATION_RE.search(evidence)
    location = location_match.group(0) if location_match else ""
    fixture_id = _sports_fixture_id(evidence) if event_type == "SPORTS_INTERRUPTION" else ""
    canonical_event_id = ""
    if event_type == "SPORTS_INTERRUPTION":
        canonical_event_id = _sports_event_signature(
            _sports_lifecycle_id(subject, cause),
            location=location,
            fixture_id=fixture_id,
            temporal=temporal,
        )
    fact_roles = {fact.role for fact in facts}
    if event_type == "RECRUITMENT_COMPETITION":
        fact_complete = {
            "COMPETITION_RATIO",
            "SELECTION_COUNT",
            "APPLICANT_COUNT",
        }.issubset(fact_roles)
        needs_enrichment = "COMPETITION_RATIO" in fact_roles and not fact_complete
    elif event_type == "AWARD_CHART":
        chart_result = bool({"CHART_RANK", "STREAK_WEEKS"}.intersection(fact_roles))
        fact_complete = chart_result and not is_low_value_popularity_poll(evidence)
        needs_enrichment = chart_result and not fact_complete
    elif event_type == "SPORTS_INTERRUPTION":
        fact_complete = bool(subject and temporal_state)
        needs_enrichment = bool(subject and not temporal_state)
    elif event_type == "SPORTS_RESULT":
        result_roles = {"AWARD", "GAME_SCORE", "HOME_RUN_COUNT", "RBI_COUNT"}
        fact_complete = bool(subject and event_action and fact_roles.intersection(result_roles))
        needs_enrichment = bool(event_action and fact_roles.intersection(result_roles) and not fact_complete)
    elif event_type in {"MARKET", "MARKET_MOVE"}:
        fact_complete = bool(observations and any(item.direction for item in observations))
        needs_enrichment = not fact_complete
    elif event_type in {"STATISTIC", "EARNINGS"}:
        fact_complete = bool(observations)
        needs_enrichment = not observations
    elif event_type == "INDUSTRY_CHANGE":
        # INDUSTRY_CHANGE is admissible only when the event owns at least one
        # source-explicit material relationship.  The generic fallback below
        # would mark a bare number plus an action as complete and force
        # synthesis to invent a binding.
        material_roles = {
            "INVESTMENT_AMOUNT",
            "ACQUISITION_AMOUNT",
            "STRATEGY_AMOUNT",
            "CONTRACT_QUANTITY",
            "PRODUCTION_QUANTITY",
            "PRODUCTION_CHANGE",
            "RATIO_CHANGE",
            "COMPARISON",
            "TREND_CHANGE",
            "EVENT_RELATION",
        }
        fact_complete = bool(subject and event_action and fact_roles.intersection(material_roles))
        needs_enrichment = bool(subject and event_action and not fact_complete)
    else:
        fact_complete = bool(subject and event_action and (date or lead_text or observations or facts))
        needs_enrichment = bool(subject and event_action and not fact_complete)
    canonical_conflict = "DATE_CONFLICT" if date_conflict else conflict_state
    signature = (
        _sports_event_signature(
            canonical_event_id,
            state=temporal_state,
        )
        if event_type == "SPORTS_INTERRUPTION"
        else canonical_event_signature(
            event_type,
            title_text,
            lead=lead_text,
            subject=subject,
            action=event_action,
        )
    )
    fact_owner_ids = tuple(dict.fromkeys(evidence_owner_ids[:1]))
    facts = tuple(
        replace(
            fact,
            evidence_owner_ids=fact.evidence_owner_ids or fact_owner_ids,
            canonical_event_id=fact.canonical_event_id or canonical_event_id or signature,
        )
        for fact in facts
    )
    focus_terms = primary_event_focus_terms(event_type, title_text, subject, facts)
    return CanonicalEvent(
        event_type=event_type,
        subject=subject,
        action=event_action,
        actor=policy.actor or subject,
        object=policy.object or (relation_fact.object if relation_fact is not None else ""),
        condition=policy.condition,
        date=date,
        period=(observations[0].period if observations else ""),
        metric=(observations[0].metric if observations else ""),
        value=(observations[0].value if observations else ""),
        direction=(observations[0].direction if observations else ""),
        observations=observations,
        facts=facts,
        evidence_detail=lead_text,
        location=location,
        temporal_state=temporal_state,
        temporal_facts=temporal,
        cause=cause,
        fixture_id=fixture_id,
        canonical_event_id=canonical_event_id or signature,
        fact_complete=fact_complete,
        needs_enrichment=needs_enrichment,
        event_signature=signature,
        conflict_state=canonical_conflict,
        evidence_owner_ids=tuple(dict.fromkeys(evidence_owner_ids)),
        representative_evidence_id=(evidence_owner_ids or ("",))[0],
        primary_focus_terms=focus_terms,
    )


def earnings_fact_parts(text: str) -> tuple[str, str, str]:
    """Return one bound ``(period, metric, value)`` earnings observation."""

    clean = normalize_text(text)
    marker = re.search(r"\.{2,}|…|·{2,}", clean)
    if marker:
        clean = clean[: marker.start()].strip()
    metric_match = _EARNINGS_METRIC_RE.search(clean)
    if metric_match is None:
        return "", "", ""
    value_match = _EARNINGS_VALUE_RE.search(clean, metric_match.end())
    if value_match is None or value_match.start() - metric_match.end() > 32:
        return "", "", ""
    period_matches = list(_EARNINGS_PERIOD_RE.finditer(clean[: metric_match.start()]))
    period = period_matches[-1].group(0).replace(" ", "") if period_matches else ""
    metric = metric_match.group(0)
    value = value_match.group(0).replace(" ", "")
    if value.endswith(("%", "퍼센트")):
        # A percentage is not an earnings amount by itself.  ``매출 85%``
        # could mean growth, mix, utilization, or a clipped comparison.  It
        # becomes a safe observation only when the same clause binds an
        # explicit direction to it (``매출 85% 증가``).
        direction = _DIRECTION_RE.search(clean[value_match.end() : value_match.end() + 24])
        if direction is None:
            return "", "", ""
    return period, metric, value


def earnings_observations(text: str) -> tuple[MetricObservation, ...]:
    """Represent a fact-rich earnings claim using the shared observation type."""

    period, metric, value = earnings_fact_parts(text)
    if not metric or not value:
        return ()
    clean = normalize_text(text)
    metric_start = clean.find(metric)
    subject = clean[:metric_start] if metric_start >= 0 else ""
    for period_marker in _EARNINGS_PERIOD_RE.finditer(subject):
        subject = subject[: period_marker.start()]
    subject = _earnings_subject(subject)
    if not subject:
        return ()
    value_match = re.search(re.escape(value), clean)
    direction_match = (
        _DIRECTION_RE.search(clean[value_match.end() : value_match.end() + 24])
        if value_match is not None
        else None
    )
    return (
        MetricObservation(
            instrument=subject,
            metric=metric,
            value=value,
            direction=direction_match.group(0).replace(" ", "") if direction_match else "",
            period=period,
            raw=clean,
        ),
    )



def _earnings_subject(value: str) -> str:
    """Keep the company/entity before a metric, not headline decoration.

    Search headlines often put a quoted slogan, a comma-separated product
    descriptor, or an AI/GPU performance clause before the actual company. The
    metric binding remains unchanged; only the subject is normalized to the
    nearest fact-bearing entity prefix.
    """

    candidate = normalize_text(value).strip(" ,·-—")
    candidate = re.sub(r"^\s*[\"'“‘][^\"'”’]*[\"'”’]\s*", "", candidate)
    candidate = re.split(r"[,，:：|｜]", candidate, maxsplit=1)[0].strip(" ,·-—")
    candidate = re.split(
        r"\s+(?=(?:20\d{2}\s?년\s?)?(?:[1-4]\s?분기|상반기|하반기|연간)\b)",
        candidate,
        maxsplit=1,
    )[0].strip(" ,·-—")
    candidate = re.sub(r"^(?:올해|이번|지난해|내년)\s+", "", candidate)
    candidate = _EARNINGS_DESCRIPTOR_RE.sub("", candidate).strip(" ,·-—")
    if not candidate:
        return ""
    return candidate

def _instrument_matches(text: str) -> list[tuple[int, int, str]]:
    normalized = normalize_text(text)
    matches: list[tuple[int, int, str]] = []
    for instrument, aliases in _MARKET_INSTRUMENTS:
        # Company names are market instruments only when the text also
        # carries explicit market context.  Without this guard, an earnings
        # headline such as ``삼성전자 2분기 영업이익 10조원`` is misread as a
        # market observation whose value is ``2분``.
        if instrument in _CORPORATE_MARKET_INSTRUMENTS and not any(
            marker in normalized for marker in _CORPORATE_MARKET_CONTEXT
        ):
            continue
        for alias in aliases:
            for match in re.finditer(re.escape(alias), normalized, re.IGNORECASE):
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
    shared_period = ""
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
        # Bind a period to the observation's own clause.  The old fallback to
        # the whole headline could attach a later instrument's month to an
        # earlier value (or copy an unrelated first month to every metric).
        prefix_start = instruments[index - 1][1] if index else 0
        prefix = value[prefix_start:start]
        prefix_periods = list(_PERIOD_RE.finditer(prefix))
        segment_periods = list(_PERIOD_RE.finditer(segment[: number_match.start()]))
        period_match = (segment_periods or prefix_periods)
        period = re.sub("\\s+", "", period_match[-1].group(0)) if period_match else ""
        if index == 0 and period:
            shared_period = period
        elif index > 0 and not period and shared_period and not prefix_periods:
            # A single period placed before a comma-separated metric list is
            # safe to inherit; an explicit period in this clause is not.
            period = shared_period
        observations.append(
            MetricObservation(
                instrument=instrument,
                metric="CHANGE" if direction else "LEVEL",
                value=number,
                direction=direction,
                period=period,
                raw=value[start:segment_end].strip(" ,·-—"),
            )
        )
    return tuple(observations)


def event_observations(event_type: str, text: str) -> tuple[MetricObservation, ...]:
    """Return typed observations for the event family being assessed."""

    if event_type == "EARNINGS":
        return earnings_observations(text)
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        return metric_observations(text)
    return ()


def event_action_signal(event_type: str, title: str, lead: str = "") -> str:
    """Return an action/fact signal accepted by the event-family contract."""

    text = f"{title} {lead}".strip()
    relation = typed_event_relation(title)
    if relation is not None and relation[0] == event_type:
        return relation[1].relation
    if event_type == "SPORTS_INTERRUPTION":
        state, _ = sports_interruption_state(event_type, text)
        return {
            "INTERRUPTED": "중단",
            "CANCELLED": "취소",
            "RESUMING": "재개",
            "RESUMED": "재개",
        }.get(state, "")
    if event_type == "POLICY":
        roles = policy_roles(title, lead)
        if roles.action:
            return roles.action
    if event_type in {"MARKET", "MARKET_MOVE"}:
        observations = metric_observations(title)
        return next((item.direction for item in observations if item.direction), "") or market_direction(text)
    if event_type == "STATISTIC":
        observations = metric_observations(title)
        directional = next((item.direction for item in observations if item.direction), "")
        if directional:
            return directional
    if event_type == "AWARD_CHART":
        if any(fact.role in {"CHART_RANK", "STREAK_WEEKS"} for fact in award_chart_facts(text)):
            return "순위 기록"
        for term in ("수상", "우승", "관왕", "기록"):
            if contains_intent_term(text, term):
                return term
        return ""
    if event_type == "PRODUCT_RELEASE":
        for term in _EVENT_ACTION_CONTRACTS[event_type]:
            if contains_intent_term(text, term):
                return term
        return ""
    if event_type == "ROSTER_PERSONNEL":
        if roster_selection_action_supported(text):
            return "선발"
        for term in ("엔트리", "부상", "트레이드", "등록", "말소"):
            if contains_action(text, term):
                return term
        return ""
    terms = _EVENT_ACTION_CONTRACTS.get(event_type, ACTION_TERMS)
    if event_type == "INDUSTRY_CHANGE":
        if industry_trend_fact(title) is not None:
            return "확산"
        # Industry headlines often use a relation such as ``투자 유치`` or
        # ``생산 확대``.  The terminal action carries the event state more
        # precisely than whichever vocabulary term happens to be listed
        # first, while retaining the shared boundary-aware matcher.
        matches = [
            (match.start(), len(term), term)
            for term in _INDUSTRY_MATERIAL_ACTIONS
            for match in (re.search(rf"(?<![{_WORD_CHAR}]){re.escape(term)}", text),)
            if match
        ]
        if matches:
            return max(matches, key=lambda value: (value[0], value[1]))[2]
    for term in terms:
        matched = contains_action(text, term) if term in ACTION_TERMS else contains_intent_term(text, term)
        if matched:
            return term
    return ""


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


def event_dates(text: str, event_type: str = "", state: str = "") -> tuple[str, ...]:
    """Return only dates close to an event marker in trusted evidence."""

    facts = temporal_facts(text, event_type)
    if event_type == "SPORTS_INTERRUPTION":
        primary = _primary_event_date(facts, event_type, state)
        return (primary,) if primary else ()
    # Preserve the established generic-event rule: one date nearest to an
    # event marker per sentence.  Only the unsafe duration/date collapse is
    # removed here; non-sports date precedence otherwise remains unchanged.
    value = normalize_text(text)
    result: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", value):
        occupied = [
            match.span()
            for pattern in (_DURATION_RE, _ELAPSED_DURATION_RE)
            for match in pattern.finditer(sentence)
        ]
        matches = [
            match
            for match in _DATE_RE.finditer(sentence)
            if not _span_overlaps(match.span(), occupied)
        ]
        markers = [
            match.start()
            for marker in _EVENT_DATE_MARKERS
            for match in re.finditer(re.escape(marker), sentence)
        ]
        if matches and markers:
            match = min(
                matches,
                key=lambda item: min(abs(item.start() - marker) for marker in markers),
            )
            result.append(re.sub(r"\s+", "", match.group(0)))
    return tuple(dict.fromkeys(result))


def canonical_event_date(
    title: str,
    lead: str = "",
    *,
    event_type: str = "",
    state: str = "",
) -> tuple[str, bool]:
    """Prefer the title event date and flag disagreement with its lead."""

    title_dates = event_dates(title, event_type, state)
    lead_dates = event_dates(lead, event_type, state)
    relative = {"어제", "오늘", "내일", "모레"}
    absolute_disagreement = (
        title_dates
        and lead_dates
        and not set(title_dates).intersection(lead_dates)
        and not (set(title_dates) & relative or set(lead_dates) & relative)
    )
    if absolute_disagreement:
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
        or _RECRUITMENT_RATIO_RE.search(value)
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

    state, cause = sports_interruption_state(event_type, f"{title} {lead}")
    date, date_conflict = canonical_event_date(title, lead, event_type=event_type, state=state)
    observations = event_observations(event_type, title)
    if observations and event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"}:
        bound = ";".join(
            ":".join(
                part
                for part in (
                    observation.instrument,
                    observation.metric,
                    observation.value,
                    observation.direction,
                    observation.period,
                )
                if part
            )
            for observation in observations[:3]
        )
        parts = (event_type, bound, date)
        return "|".join(part for part in parts if part)
    if event_type == "SPORTS_INTERRUPTION":
        league = subject or _event_subject(event_type, title, ())
        evidence = f"{title} {lead}"
        temporal = temporal_facts(evidence, event_type)
        location_match = _LOCATION_RE.search(evidence)
        canonical_event_id = _sports_event_signature(
            _sports_lifecycle_id(league, cause),
            location=location_match.group(0) if location_match else "",
            fixture_id=_sports_fixture_id(evidence),
            temporal=temporal,
        )
        return _sports_event_signature(
            canonical_event_id,
            state=state,
        )
    if event_type == "SPORTS_RESULT":
        facts = sports_result_facts(f"{title} {lead}")
        fact_map = {fact.role: fact.value for fact in facts}
        entity = subject or _event_subject(event_type, title, (), lead)
        if fact_map.get("AWARD"):
            identity = (fact_map["AWARD"], fact_map.get("PERIOD", ""))
        elif fact_map.get("GAME_SCORE"):
            identity = (fact_map["GAME_SCORE"], date)
        else:
            identity = (
                fact_map.get("HOME_RUN_COUNT", ""),
                fact_map.get("RBI_COUNT", ""),
                fact_map.get("PERIOD", ""),
            )
        parts = (event_type, compact(entity), *(compact(value) for value in identity))
        return "|".join(part for part in parts if part)
    if event_type.startswith("RECRUITMENT"):
        facts = recruitment_facts(f"{title} {lead}")
        ratio = next((fact.value for fact in facts if fact.role == "COMPETITION_RATIO"), "")
        entity = subject or _event_subject(event_type, title, ())
        parts = (event_type, compact(entity), ratio, date)
        return "|".join(part for part in parts if part)
    if event_type == "AWARD_CHART":
        facts = award_chart_facts(f"{title} {lead}")
        rank = next((fact.value for fact in facts if fact.role == "CHART_RANK"), "")
        entity = subject or _event_subject(event_type, title, ())
        parts = (event_type, compact(entity), rank, date)
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
    headline_numbers = {compact(value) for value in _NUMBER_RE.findall(headline)}
    summary_numbers = {compact(value) for value in _NUMBER_RE.findall(summary)}
    new_numbers = summary_numbers - headline_numbers
    headline_dates = {compact(value) for value in _DATE_RE.findall(headline)}
    summary_dates = {compact(value) for value in _DATE_RE.findall(summary)}
    new_dates = summary_dates - headline_dates
    # A number/date only counts when it is genuinely new relative to the
    # headline. Repeating the same metric in declarative form is not
    # information gain, and must not rescue a headline-copy summary.
    has_new_fact = bool(new_numbers or new_dates)
    return bool(has_new_fact or len(meaningful_additional) >= 2)
