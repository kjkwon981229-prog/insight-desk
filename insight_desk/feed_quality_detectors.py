from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

# Keep the accumulated low-level detector implementation byte-for-byte intact.
# This public façade adds only measured live-surface regressions; admission policy
# composition remains exclusively in story_admission.py.
from insight_desk._feed_quality_detectors_impl import *  # noqa: F401,F403
from insight_desk import _feed_quality_detectors_impl as _impl


# A deictic event mention is standalone only when its visible text has already
# introduced an event antecedent. Model the discourse relation, not one particle
# surface: 이번/해당/이 행사 + subject/object/location/topic particles are the
# same unresolved referent family.
_DEICTIC_EVENT_REFERENCE_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:이번|해당|이)\s+(?P<head>행사)"
    r"(?:은|는|이|가|을|를|의|에|에서|에는|로|으로)?(?=\s|$)"
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
_BARE_ROLE_LEAD_RE = re.compile(
    r"^(?:책임자|관계자|당국자|담당자|실무자|전문가)(?:들)?(?:은|는|이|가)(?=\s|$)"
)
_SUBJECTLESS_STOCK_TO_COMPANY_RE = re.compile(
    r"^주가(?:는|가)?[^.!?。！？,，]{0,100}(?:가운데|상황에서|속에서)?\s*[,，]\s*"
    r"(?:(?:이|해당|그)\s+)?회사(?:는|가|의)(?:\s|$)"
)
_ORPHANED_TEST_REFERENCE_RE = re.compile(r"(?:^|\s)해당\s+테스트(?:에|에서|를|는|가|의|\s)")
_INTERPRETIVE_BACKGROUND_END_RE = re.compile(
    r"(?:상징적으로\s+)?(?:드러낸|보여주는)\s+(?:표현|사례|대목)(?:이다|입니다)$"
)
_GENERIC_MARKET_COGNITION_RE = re.compile(
    r"^(?:시장(?:은|이|에서는)|증시(?:는|가|에서는)|"
    r"투자자(?:들)?(?:은|는|이|가)|시장\s+참여자(?:들)?(?:은|는|이|가))\s+"
    r"[^.!?。！？]{0,260}?"
    r"(?:보고\s+있다|보고\s+있습니다|평가한다|평가하고\s+있다|평가하고\s+있습니다|"
    r"판단한다|판단하고\s+있다|해석한다|해석하고\s+있다|"
    r"주목하고\s+있다|주목하고\s+있습니다|기대하고\s+있다|기대하고\s+있습니다)$"
)
_ABSTRACT_EMERGENCE_ATTENTION_RE = re.compile(
    r"(?:모델|방식|전략|흐름|움직임)(?:이|가)\s+"
    r"(?:새로\s+)?(?:등장|나타나|확산)(?:해|하며|하면서|하고|했다|하고\s+있)[^.!?。！？]{0,140}?"
    r"(?:이목|관심|주목)(?:을|이)?\s*(?:모으|끌)"
)
_CONDITIONAL_EXPECTED_BENEFIT_RE = re.compile(
    r"(?:하면|할\s+경우|한다면)\s*[^.!?。！？]{0,180}?"
    r"(?:도움(?:이|을)?\s+될|기여할|활성화(?:에|를)?\s+도움|효과(?:가|를)?\s+(?:있|낼))"
    r"[^.!?。！？]{0,100}?(?:것으로\s+)?"
    r"(?:기대됐|기대된다|기대됩니다|전망됐|전망된다|전망됩니다)"
)
_ROLLING_SPORTS_FORM_RE = re.compile(
    r"최근\s+\d+\s*경기(?:에서|는|동안)?[^.!?。！？]{0,70}?\d+\s*승\s*\d+\s*패"
)
_ROLLING_SPORTS_FORM_END_RE = re.compile(
    r"(?:기록했다|기록하였다|기록했습니다|그쳤다|그쳤습니다)$"
)
_AI_PREVIEW_PUBLISHER_NOTICE_RE = re.compile(
    r"^\*?\s*위\s+내용은\s+생성형\s+AI로\s+예측한\s+경기\s+분석(?:\s|$)",
    flags=re.IGNORECASE,
)
_COMPONENT_FEATURE_SUBJECT_RE = re.compile(
    r"^(?:[가-힣A-Za-z0-9·-]+\s+){0,5}"
    r"(?:팝업\s+전시|전시|부스|체험존|전시관|체험\s+공간|프로그램)"
    r"(?:은|는|이|가)(?=\s)"
)
_COMPONENT_FEATURE_END_RE = re.compile(
    r"(?:제공한다|제공합니다|지원한다|지원합니다|운영한다|운영합니다|"
    r"구성된다|구성됩니다)$"
)
_COMPONENT_CURRENT_EVENT_RE = re.compile(
    r"(?:개막|개최|오픈|문을\s+열|출시|공개|발표|도입|신설|시작|선보였|선보인다)"
)
_LEADING_TIMESTAMP_CHROME_RE = re.compile(
    r"^\s*[-–—]?\s*(?:입력|기사입력|등록|수정|업데이트)\s+"
    r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}(?:\s+\d{1,2}:\d{2})?(?=\s|$)",
    flags=re.IGNORECASE,
)
_SQUARE_BRACKET_BYLINE_RE = re.compile(
    r"\[[^\]\n=]{1,50}=[^\]\n]{1,50}\s+(?:기자|특파원)\]"
)
_STATIC_COMPANY_CAPABILITY_RE = re.compile(
    r"(?:\d[\d,.]*(?:만|천|백)?\s*점\s+이상|\d[\d,.]*\s*개(?:의)?)"
    r"\s*(?:의\s+)?(?:제품|의료기기|품목)"
    r"[^.!?。！？]{0,90}?(?:취급|보유|운영)"
    r"[^.!?。！？]{0,50}?(?:한다|하고\s+있|덧붙였)"
)
_STATIC_CAPABILITY_CURRENT_EVENT_RE = re.compile(
    r"(?:\d{1,2}일|계약|체결|출시|공개|발표|도입|신규|시작|확대했|추가했)"
)
_STATIC_PRODUCT_DEFINITION_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&()/_+-]{2,60}(?:은|는|이|가)\s+"
    r"[^.!?。！？]{1,240}?(?:솔루션|플랫폼|서비스|제품)(?:이다|입니다)$"
)
_ALBUM_NARRATIVE_SYNOPSIS_RE = re.compile(
    r"(?:이야기|서사|메시지)(?:가|를|은|는)?"
    r"[^.!?。！？]{0,80}?(?:앨범|음반)(?:에|에는)"
    r"[^.!?。！？]{0,30}?(?:담겼|담았|담아냈)"
)
_ALBUM_CURRENT_EVENT_RE = re.compile(
    r"(?:\d{1,2}일|발매|출시|공개|컴백|활동\s+시작|계획을\s+공개|계획을\s+발표)"
)
_MULTI_VOTE_COUNT_RE = re.compile(r"(?<!\d)\d[\d,]*\s*표")
_MULTI_CATEGORY_TOP_RESULT_RE = re.compile(
    r"\d+\s*개\s*부문\s*TOP\s*\d+\s*에\s*들었다$",
    flags=re.IGNORECASE,
)
_NAMED_HEADLINE_LEAD_RE = re.compile(r"^[가-힣A-Za-z0-9·&()/_+-]{2,40},\s")
_EXPLICIT_VISIBLE_SUBJECT_RE = re.compile(
    r"(?:^|\s)[가-힣A-Za-z0-9·&()/_+-]{2,40}(?:은|는|이|가)(?=\s)"
)
_GENERIC_ALBUM_TRACKLIST_HEADLINE_RE = re.compile(
    r"^(?:앨범|음반)\s+(?:수록곡|트랙(?:리스트)?)\s+\d+\s*곡(?:\s+(?:공개|수록))?$"
)
_BARE_ALBUM_TRACKLIST_SUMMARY_RE = re.compile(
    r"\d+\s*곡(?:이|은|을)?\s+(?:앨범|음반)에\s+수록(?:됐|되었|됐다|되었다|돼)"
)
_EXPLICIT_RESEARCH_RELEASE_DATE_RE = re.compile(
    r"(?:(?P<year>20\d{2})년\s*)?(?:지난\s+)?"
    r"(?P<month>1[0-2]|0?[1-9])월\s*(?P<day>3[01]|[12]\d|0?[1-9])일\s+"
    r"[^.!?。！？]{0,80}?(?:공개한|발표한|발간한|출간한)\s+"
    r"(?:보고서|조사|분석|연구|자료)"
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
_UNATTRIBUTED_EVALUATIVE_STATE_ENDINGS = (
    "꼽힌다",
    "꼽힙니다",
    "꼽히고 있다",
    "꼽히고 있습니다",
    "거론된다",
    "거론됩니다",
    "거론되고 있다",
    "거론되고 있습니다",
    "지목된다",
    "지목됩니다",
    "지목되고 있다",
    "지목되고 있습니다",
)


def _orphaned_referential_event(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    for match in _DEICTIC_EVENT_REFERENCE_RE.finditer(normalized):
        head = match.group("head")
        prefix = normalized[: match.start()].rstrip(" ,:;·")
        if not prefix:
            return True
        # Resolve a prior visible event noun even when Korean case/topic particles
        # are attached to it (`행사를`, `행사에서`, ...). This is lexical antecedent
        # resolution, not acceptance of a bare deictic reference.
        antecedent = re.compile(
            rf"(?<![가-힣A-Za-z0-9]){re.escape(head)}"
            r"(?:에서|에는|으로|은|는|이|가|을|를|의|에|로)?"
            r"(?=\s|[,.!?。！？]|$)"
        )
        if antecedent.search(prefix) is not None:
            continue
        return True
    return False


def _orphaned_visible_actor(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _GENERIC_LABOR_MANAGEMENT_RE.search(normalized) is not None
        or _REFERENTIAL_REPORT_LEAD_RE.search(normalized) is not None
        or _GENERIC_COMPANY_LEAD_RE.search(normalized) is not None
        or _BARE_ROLE_LEAD_RE.search(normalized) is not None
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


def _publisher_ai_preview_notice(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return _AI_PREVIEW_PUBLISHER_NOTICE_RE.search(normalized) is not None


def _component_feature_state(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _COMPONENT_FEATURE_SUBJECT_RE.search(primary) is None:
        return False
    if _COMPONENT_CURRENT_EVENT_RE.search(primary) is not None:
        return False
    return _COMPONENT_FEATURE_END_RE.search(primary) is not None


def _visible_extraction_chrome(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _LEADING_TIMESTAMP_CHROME_RE.search(normalized) is not None
        or _SQUARE_BRACKET_BYLINE_RE.search(normalized) is not None
    )


def _static_company_capability(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _STATIC_COMPANY_CAPABILITY_RE.search(primary) is None:
        return False
    return _STATIC_CAPABILITY_CURRENT_EVENT_RE.search(primary) is None


def _static_product_definition(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _STATIC_PRODUCT_DEFINITION_RE.search(primary) is None:
        return False
    return _STATIC_CAPABILITY_CURRENT_EVENT_RE.search(primary) is None


def _context_free_album_synopsis(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    if not primary or _ALBUM_NARRATIVE_SYNOPSIS_RE.search(primary) is None:
        return False
    return _ALBUM_CURRENT_EVENT_RE.search(primary) is None


def _actorless_multi_vote_ranking(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if len(_MULTI_VOTE_COUNT_RE.findall(normalized)) < 2:
        return False
    if _MULTI_CATEGORY_TOP_RESULT_RE.search(normalized) is None:
        return False
    first_vote = _MULTI_VOTE_COUNT_RE.search(normalized)
    if first_vote is None:
        return False
    prefix = normalized[: first_vote.start()].strip()
    if _NAMED_HEADLINE_LEAD_RE.search(normalized) is not None:
        return False
    return _EXPLICIT_VISIBLE_SUBJECT_RE.search(prefix) is None


def _unidentified_album_tracklist(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if _GENERIC_ALBUM_TRACKLIST_HEADLINE_RE.search(normalized) is not None:
        return True
    if not normalized.startswith(("‘", "'", "“", '"')):
        return False
    return _BARE_ALBUM_TRACKLIST_SUMMARY_RE.search(normalized) is not None


def _stale_explicit_research_release(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    normalized = " ".join(value.split()).strip()
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for match in _EXPLICIT_RESEARCH_RELEASE_DATE_RE.finditer(normalized):
        year_text = match.group("year")
        year = int(year_text) if year_text is not None else reference.year
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            candidate = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        if year_text is None and candidate > reference + timedelta(hours=6):
            try:
                candidate = candidate.replace(year=year - 1)
            except ValueError:
                continue
        if candidate > reference + timedelta(hours=6):
            continue
        if reference - candidate > timedelta(hours=72):
            return True
    return False


def visible_metadata_text(value: str) -> bool:
    return (
        _impl.visible_metadata_text(value)
        or _publisher_ai_preview_notice(value)
        or _visible_extraction_chrome(value)
    )


def publisher_notice_boilerplate(value: str) -> bool:
    return _impl.publisher_notice_boilerplate(value) or _publisher_ai_preview_notice(value)


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
        or _actorless_multi_vote_ranking(normalized)
        or _unidentified_album_tracklist(normalized)
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
        or _unidentified_album_tracklist(normalized)
    )


def stale_explicit_past_event_text(
    value: str,
    *,
    now: datetime | None = None,
) -> bool:
    return _impl.stale_explicit_past_event_text(value, now=now) or _stale_explicit_research_release(
        value, now=now
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
    primary = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)[0].strip()
    rolling_form_only = (
        _ROLLING_SPORTS_FORM_RE.search(primary) is not None
        and _ROLLING_SPORTS_FORM_END_RE.search(primary) is not None
    )
    return (
        _impl.non_event_analytical_text(normalized)
        or _INTERPRETIVE_BACKGROUND_END_RE.search(normalized) is not None
        or normalized.endswith(_UNATTRIBUTED_EVALUATIVE_STATE_ENDINGS)
        or _GENERIC_MARKET_COGNITION_RE.search(normalized) is not None
        or _ABSTRACT_EMERGENCE_ATTENTION_RE.search(normalized) is not None
        or _CONDITIONAL_EXPECTED_BENEFIT_RE.search(primary) is not None
        or rolling_form_only
        or _component_feature_state(primary)
        or _static_company_capability(primary)
        or _static_product_definition(primary)
        or _context_free_album_synopsis(primary)
    )


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.malformed_visible_text(normalized)
        or _MALFORMED_KBO_LEAGUE_YEAR_RE.search(normalized) is not None
        or normalized.endswith("·")
    )
