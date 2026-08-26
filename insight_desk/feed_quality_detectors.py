from __future__ import annotations

import re

# Keep the accumulated low-level detector implementation byte-for-byte intact.
# This public façade adds only measured live-surface regressions; admission policy
# composition remains exclusively in story_admission.py.
from insight_desk._feed_quality_detectors_impl import *  # noqa: F401,F403
from insight_desk import _feed_quality_detectors_impl as _impl


_ORPHANED_REFERENTIAL_EVENT_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&() ._-]{2,48}(?:은|는|,)?\s*이번\s+행사(?:에서|에는|에)(?:\s|$)"
)
_SUBJECTLESS_MARKET_HEADLINE_RE = re.compile(
    r"^장\s+(?:초반|중반|후반)\s+\d+(?:\.\d+)?%\s+(?:넘게\s+)?"
    r"(?:떨어지|오르|하락|상승)"
)
_MALFORMED_KBO_LEAGUE_YEAR_RE = re.compile(
    r"(?<!\d)\d{3}\s+신한(?:은행)?\s+(?:SOL(?:\s+Bank)?\s+)?KBO리그"
)
_GENERIC_LABOR_MANAGEMENT_RE = re.compile(r"^노사(?:는|가|의|,|\s)")
_REFERENTIAL_REPORT_LEAD_RE = re.compile(r"^(?:같은\s+)?보도(?:는|가)(?:\s|$)")
_GENERIC_COMPANY_LEAD_RE = re.compile(r"^(?:(?:이|해당|그)\s+)?회사(?:는|가|의)(?:\s|$)")
_SUBJECTLESS_STOCK_TO_COMPANY_RE = re.compile(
    r"^주가(?:는|가)?[^.!?。！？,，]{0,100}(?:가운데|상황에서|속에서)?\s*[,，]\s*"
    r"(?:(?:이|해당|그)\s+)?회사(?:는|가|의)(?:\s|$)"
)
_ORPHANED_TEST_REFERENCE_RE = re.compile(r"(?:^|\s)해당\s+테스트(?:에|에서|를|는|가|의|\s)")
_INTERPRETIVE_BACKGROUND_END_RE = re.compile(
    r"(?:상징적으로\s+)?(?:드러낸|보여주는)\s+(?:표현|사례|대목)(?:이다|입니다)$"
)
_KBO_TEAM_RE = re.compile(
    r"(?:한화(?:\s+이글스)?|SSG(?:\s*랜더스)?|KIA(?:\s*타이거즈)?|LG(?:\s*트윈스)?|"
    r"두산(?:\s*베어스)?|롯데(?:\s*자이언츠)?|삼성(?:\s*라이온즈)?|KT(?:\s*위즈)?|"
    r"NC(?:\s*다이노스)?|키움(?:\s*히어로즈)?)",
    flags=re.IGNORECASE,
)
_KBO_GENERIC_RESULT_RE = re.compile(
    r"(?:경기\s*(?:에서\s*)?(?:패배|승리)|경기를\s+(?:내주었|내줬|내주었다|이겼|승리했))"
)
_KBO_SCORE_RE = re.compile(r"(?<!\d)\d{1,2}\s*(?:대|[-:])\s*\d{1,2}(?!\d)")
_KBO_DAY_RE = re.compile(r"(?<!\d)(?:[0-3]?\d)일(?!\s*(?:간|동안|후|뒤|째))")

# Discourse references are handled as a syntactic family instead of extending one
# live-specific noun blacklist. Measure-like heads still form a semantic class because
# a bare "이/그/해당 + measure" requires a visible value or prior lexical antecedent.
_DEICTIC_MEASURE_REFERENCE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:이|그|해당)\s+"
    r"(?P<head>[가-힣A-Za-z0-9·_-]{1,20})"
    r"(?:은|는|이|가|을|를|로|에|에서|의)(?=\s|$)"
)
_MEASURE_REFERENCE_HEAD_RE = re.compile(
    r"(?:수치|비율|지표|지수|값|수준|규모|금액|가격|점수|증가율|성장률|감소율|점유율|율|률)$"
)
_VISIBLE_QUANTITY_RE = re.compile(
    r"(?<!\d)\d[\d,.]*(?:\.\d+)?\s*(?:%|％|배|원|달러|명|건|개|회|점|위)?"
)

_DATE_LED_SPORTS_STAT_RE = re.compile(
    r"^(?:지난\s+)?\d{1,2}일\s+"
    r"(?P<context>.{0,220}?)"
    r"(?:경기|전)(?:에|에서)\s+"
    r".{0,100}?\d+\s*(?:타수|이닝|경기)\b"
)
_EXPLICIT_POST_DATE_SUBJECT_RE = re.compile(
    r"(?:^|\s)(?P<subject>[가-힣A-Za-z·_-]{2,24})(?:은|는|이|가)(?=\s)"
)

_RELATIVE_PAST_SPORTS_PERIOD_RE = re.compile(
    r"(?:지난해|작년|전년도|지난\s+시즌|직전\s+시즌)"
)
_RELATIVE_PAST_COMPARISON_RE = re.compile(
    r"(?:지난해|작년|전년도|지난\s+시즌|직전\s+시즌)\s*(?:보다|대비|이후|이래)"
)
_SPORTS_PERFORMANCE_RE = re.compile(
    r"(?:\d[\d,.]*\s*(?:경기|이닝|승|패|세이브|홀드|홈런|안타|타점)|평균자책점)"
)
_SPORTS_PERFORMANCE_PREDICATE_RE = re.compile(
    r"(?:기록(?:했|하|해|하며|했고|하였다|해냈)|활약(?:했|하|하며)|이끌(?:었|며)|등판(?:했|하|해))"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？]\s*")


def _orphaned_referential_event(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return _ORPHANED_REFERENTIAL_EVENT_RE.search(normalized) is not None


def _orphaned_visible_actor(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _GENERIC_LABOR_MANAGEMENT_RE.search(normalized) is not None
        or _REFERENTIAL_REPORT_LEAD_RE.search(normalized) is not None
        or _GENERIC_COMPANY_LEAD_RE.search(normalized) is not None
        or _SUBJECTLESS_STOCK_TO_COMPANY_RE.search(normalized) is not None
    )


def _orphaned_test_reference(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    match = _ORPHANED_TEST_REFERENCE_RE.search(normalized)
    if match is None:
        return False
    prefix = normalized[: match.start()].rstrip(" ,:;·")
    # A demonstrative test phrase is self-contained only when the preceding visible
    # clause has already named a concrete test/benchmark rather than merely a speaker.
    return re.search(r"(?:테스트|시험|벤치마크|평가)", prefix, flags=re.IGNORECASE) is None


def _orphaned_measure_reference(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    for match in _DEICTIC_MEASURE_REFERENCE_RE.finditer(normalized):
        head = match.group("head")
        if _MEASURE_REFERENCE_HEAD_RE.search(head) is None:
            continue
        prefix = normalized[: match.start()].rstrip(" ,:;·")
        if not prefix:
            return True
        # A preceding lexical mention resolves the same metric concept; an explicit
        # visible quantity also resolves a deictic "수치/값/비율" without requiring
        # the exact same head noun. This is discourse resolution, not a phrase ban.
        if re.search(re.escape(head), prefix, flags=re.IGNORECASE) is not None:
            continue
        if _VISIBLE_QUANTITY_RE.search(prefix) is not None:
            continue
        return True
    return False


def _date_led_subjectless_sports_stat(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    match = _DATE_LED_SPORTS_STAT_RE.search(normalized)
    if match is None:
        return False
    # A date-led statline is allowed when it still names an explicit grammatical
    # performer after the date. The live failure had only venue/league/opponent context.
    return _EXPLICIT_POST_DATE_SUBJECT_RE.search(match.group("context")) is None


def _unidentified_kbo_result(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    if _KBO_GENERIC_RESULT_RE.search(normalized) is None:
        return False
    teams = {match.group(0).casefold() for match in _KBO_TEAM_RE.finditer(normalized)}
    if len(teams) != 1:
        return False
    return _KBO_SCORE_RE.search(normalized) is None and _KBO_DAY_RE.search(normalized) is None


def context_dependent_headline(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_headline(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
        or _orphaned_test_reference(normalized)
        or _orphaned_measure_reference(normalized)
        or _date_led_subjectless_sports_stat(normalized)
        or _unidentified_kbo_result(normalized)
        or _SUBJECTLESS_MARKET_HEADLINE_RE.search(normalized) is not None
    )


def context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_summary(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
        or _orphaned_test_reference(normalized)
        or _orphaned_measure_reference(normalized)
        or _unidentified_kbo_result(normalized)
    )


def stale_relative_past_event_text(value: str) -> bool:
    if _impl.stale_relative_past_event_text(value):
        return True
    normalized = " ".join(value.split()).strip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _RELATIVE_PAST_SPORTS_PERIOD_RE.search(primary) is None:
        return False
    if _RELATIVE_PAST_COMPARISON_RE.search(primary) is not None:
        return False
    return (
        _SPORTS_PERFORMANCE_RE.search(primary) is not None
        and _SPORTS_PERFORMANCE_PREDICATE_RE.search(primary) is not None
    )


def non_event_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    return (
        _impl.non_event_analytical_text(normalized)
        or _INTERPRETIVE_BACKGROUND_END_RE.search(normalized) is not None
    )


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.malformed_visible_text(normalized)
        or _MALFORMED_KBO_LEAGUE_YEAR_RE.search(normalized) is not None
        or normalized.endswith("·")
    )
