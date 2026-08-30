from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

# Low-level story-quality detectors live here. They expose individual signals only;
# admission policy composition belongs exclusively to story_admission.py.
from insight_desk.feed_quality_detectors_core import *  # noqa: F401,F403
from insight_desk.feed_quality_detectors_core import (
    context_dependent_summary as _core_context_dependent_summary,
    metadata_or_caption_text as _core_metadata_or_caption_text,
    non_event_analytical_text as _core_non_event_analytical_text,
    stale_day_only_context as _core_stale_day_only_context,
    stale_explicit_past_event_text as _core_stale_explicit_past_event_text,
    stale_quarter_context as _core_stale_quarter_context,
    stale_relative_past_event_text as _core_stale_relative_past_event_text,
    stale_relative_period_event_text as _core_stale_relative_period_event_text,
)


_CURRENT_WEEK_AGGREGATE_CUES = (
    "집계",
    "평균",
    "경기 시간",
    "10개 구단",
    "가장 길",
    "가장 짧",
    "주간 통계",
    "주간 기록",
)
_PRIOR_PERIOD_POLICY_EVENT_RE = re.compile(
    r"(?:지난달|지난\s+달|지난\s+(?:1[0-2]|[1-9])월|지난\s+분기|지난\s+연도)"
    r"[^!?。！？]{0,180}?(?:기준금리|정책금리|금리)"
    r"[^!?。！？]{0,120}?(?:올렸|내렸|인상했|인하했|동결했)"
)
_PUBLISHER_NOTICE_PERMISSION_CUES = ("무단", "사전허가없이", "사전 허가 없이")
_PUBLISHER_NOTICE_RESTRICTION_TERMS = ("복사", "배포", "전재", "재배포", "판매")
_PUBLISHER_NOTICE_LEGAL_CUES = ("책임", "금지", "저작권")
_SPORTS_CONTEXT_CUES = ("경기에서", "전에서", "경기 중", "경기에", "경기,")
_SPORTS_DEPICTIVE_ACTION_CUES = (
    "투구",
    "공을 던지",
    "타격",
    "수비",
    "훈련",
    "캐치볼",
    "몸을 풀",
    "세리머니",
    "포즈",
)
_SPORTS_DEPICTIVE_ACTION_RE = re.compile(
    r"(?:공을\s+[^.!?。！？]{0,24}?던지고\s+있|마운드[^.!?。！？]{0,40}?던지고\s+있)"
)
_SPORTS_DEPICTIVE_ENDINGS = ("고 있다", "고 있다.", "고 있습니다", "고 있습니다.")
_CONTEXTUAL_LIST_LEADS = ("가장 먼저,", "먼저,")
_REFERENTIAL_CONTENT_LEAD_RE = re.compile(
    r"^(?:이|해당)\s+(?:앨범|음반|싱글|곡|EP|제품|공간|시설)(?:은|는|이|가)(?:\s|$)"
)
_TRAILING_DATELINE_BYLINE_RE = re.compile(
    r"(?:^|[.!?。！？]\s*)[\(（][^()（）]{1,60}=[^()（）]{1,60}[\)）]\s*"
    r"[가-힣]{2,4}\s+(?:기자|특파원)$"
)
_LEADING_DATELINE_BYLINE_RE = re.compile(
    r"^[\(（][^()（）]{1,80}=[^()（）]{1,80}[\)）]\s*"
    r"[가-힣]{2,4}\s+(?:기자|특파원)\s*=\s*"
)

_PRIMARY_CURRENT_EVENT_CUES = (
    "발표",
    "공개",
    "출시",
    "도입",
    "시행",
    "개정",
    "변경",
    "확정",
    "결정",
    "체결",
    "유치",
    "투자",
    "인수",
    "선발",
    "접수",
    "합격",
    "수상",
    "공연",
    "개최",
    "실시",
    "진행",
    "기록",
    "조사",
    "응답",
    "상승",
    "하락",
    "증가",
    "감소",
)
_PRIMARY_GOAL_RE = re.compile(
    r"(?:목표|목적|지향점|방향)(?:으?로)?[^.!?。！？]{0,24}?(?:한다|삼는다|두고\s*있다|이다)$"
)
_PRIMARY_NORMATIVE_ENDINGS = (
    "해야 한다",
    "하여야 한다",
    "충족해야 한다",
    "적용해야 한다",
    "필요하다",
    "요구된다",
    "준수해야 한다",
    "해서는 곤란하다",
    "해서는 곤란합니다",
    "해서는 안 된다",
    "해서는 안 됩니다",
)
_PRIMARY_ANALYTICAL_CUES = (
    "시각이 우세",
    "견해가 우세",
    "의견이 우세",
    "의견도 맞서",
    "의견이 맞서",
    "견해가 맞서",
    "전망이 엇갈",
    "의견이 엇갈",
    "견해가 엇갈",
    "시장 무게중심",
    "판단이 우세",
    "의미로 풀이",
    "논쟁",
)
_PRIMARY_ABSTRACT_RESPONSE_CUES = ("변화", "체계", "환경", "상황", "흐름")
_PRIMARY_RESPONSE_ENDINGS = (
    "대응한다",
    "대응하고 있다",
    "대응하고 있습니다",
    "선제적으로 대응한다",
)
_PRIMARY_COMPONENT_CONTAINER_CUES = (
    "과정",
    "프로그램",
    "교육",
    "커리큘럼",
    "항목",
    "내용",
)
_PRIMARY_COMPONENT_ENDINGS = (
    "포함한다",
    "포함하고 있다",
    "포함하고 있습니다",
    "구성된다",
    "구성돼 있다",
    "구성되어 있다",
)
_PRIMARY_GENERIC_COMPONENT_SECTION_RE = re.compile(
    r"^(?:전시\s+)?(?:분야|부문)(?:은|는|이|가)(?:\s|$)"
)
_PRIMARY_METHOD_ENDINGS = (
    "방식이다",
    "방식입니다",
    "구조다",
    "구조이다",
    "형태다",
    "형태이다",
)
_PRIMARY_ABSENCE_STATE_ENDINGS = (
    "발표되지 않았다",
    "발표되지 않았습니다",
    "발표되지 않은 상태다",
    "발표되지 않은 상태입니다",
    "공개되지 않았다",
    "공개되지 않았습니다",
    "공개되지 않은 상태다",
    "공개되지 않은 상태입니다",
    "확정되지 않았다",
    "확정되지 않았습니다",
    "확정되지 않은 상태다",
    "확정되지 않은 상태입니다",
    "결정되지 않았다",
    "결정되지 않았습니다",
    "결정되지 않은 상태다",
    "결정되지 않은 상태입니다",
    "계획이 없다",
    "계획은 없다",
    "계획이 없습니다",
    "계획은 없습니다",
    "미정이다",
    "미정입니다",
)
_PRIMARY_REFERENTIAL_PLAN_RE = re.compile(
    r"^(?:[^.!?。！？]{1,80}?(?:은|는|이|가)\s+)?(?:이번|해당)\s+"
    r"[^.!?。！？]{1,90}?(?:통해|기반으로|바탕으로)\s+"
    r"[^.!?。！？]{1,220}?(?:할|해나갈)\s+계획(?:이다|입니다)$"
)
_PRIMARY_INTENDED_USE_RE = re.compile(
    r"(?:활용|사용|운영)(?:될|할)\s+예정(?:이다|입니다)?$"
)
_PRIMARY_STATIC_RULE_CUES = ("법", "시행령", "시행규칙", "규정", "지침")
_PRIMARY_STATIC_RULE_ENDINGS = (
    "할 수 있다",
    "할 수 있습니다",
    "할 수 없다",
    "할 수 없습니다",
    "제한된다",
    "제한됩니다",
)
_PRIMARY_STATIC_ASSET_CLASSIFICATION_RE = re.compile(
    r"(?:안전자산|위험자산)(?:으)?로\s+분류[^.!?。！？]{0,180}?"
    r"(?:\d{1,3}\s*%|전액)[^.!?。！？]{0,100}?"
    r"(?:편입|투자)[^.!?。！？]{0,70}?(?:가능하다|가능합니다|할\s+수\s+있다|할\s+수\s+있습니다)$"
)
_PRIMARY_AI_TREND_STRATEGY_RE = re.compile(
    r"(?:개발자|연구자)[^.!?。！？]{0,160}?(?:늘어나|증가하|확산되)[^.!?。！？]{0,180}?"
    r"(?:전략|흐름|움직임)(?:이|가)\s+(?:등장|나타나|확산)[^.!?。！？]{0,30}?(?:했다|한다|하고\s+있다|하고\s+있습니다)$"
)
_PRIMARY_PROMOTIONAL_ROLLUP_RE = re.compile(
    r"(?:이어지는|연이은)\s+(?:컴백|복귀|발매|공개)\s+소식[^.!?。！？]{0,180}?"
    r"(?:장식|달구|기대감|관심)[^.!?。！？]{0,80}?(?:있다|있습니다|한다|합니다)$"
)
_PRIMARY_PROMOTIONAL_TRAINING_BENEFIT_RE = re.compile(
    r"(?:교육|안무교육|훈련|프로그램)[^.!?。！？]{0,120}?"
    r"(?:진행|운영)[^.!?。！？]{0,100}?"
    r"(?:전문성|협동심|자신감|역량)[^.!?。！？]{0,80}?"
    r"(?:더했다|높였다|쌓았다|키웠다)$"
)
_PRIMARY_KBO_TEAM_PARTICIPATION_RE = re.compile(
    r"^(?:한화(?:\s+이글스)?|SSG(?:\s*랜더스)?|KIA(?:\s*타이거즈)?|LG(?:\s*트윈스)?|"
    r"두산(?:\s*베어스)?|롯데(?:\s*자이언츠)?|삼성(?:\s*라이온즈)?|KT(?:\s*위즈)?|"
    r"NC(?:\s*다이노스)?|키움(?:\s*히어로즈)?)(?:은|는|이|가)"
    r"[^.!?。！？]{0,260}?(?:경기|대결)에서\s+출전했다$",
    flags=re.IGNORECASE,
)
_PRIMARY_MARKET_ATTENTION_RE = re.compile(
    r"(?:시장(?:의)?\s+)?관심(?:은|이)\s+[^.!?。！？]{0,220}?"
    r"(?:실적|실적\s+발표|발표|공개)[^.!?。！？]{0,100}?"
    r"(?:쏠리고|모이고)\s+있(?:다|습니다)$"
)
_PRIMARY_POLICY_COMMENTARY_RE = re.compile(
    r"(?:기준금리|정책금리|금리)[^.!?。！？]{0,180}?"
    r"(?:말|논리|효과|의미)(?:은|는|이|가)?[^.!?。！？]{0,100}?"
    r"(?:빛을\s+잃|힘을\s+잃|퇴색|약해지)[^.!?。！？]{0,80}?"
    r"(?:있다|있습니다|하고\s+있다|하고\s+있습니다)$"
)
_PRIMARY_UNATTRIBUTED_STATE_RE = re.compile(
    r"(?:현상|흐름|양상|움직임)(?:이|가)\s+[^.!?。！？]{0,100}?"
    r"(?:나타나고|이어지고|강화되고|확산되고)\s+있(?:다|습니다)$"
)
_PRIMARY_PERFORMANCE_EVALUATION_RE = re.compile(
    r"(?:연기|감정선|연기자|배우)[^.!?。！？]{0,180}?"
    r"(?:가능성|역량|매력)[^.!?。！？]{0,80}?"
    r"(?:드러냈다|보여줬다|보여주었다|입증했다)$"
)
_PRIMARY_CAREER_HISTORY_RE = re.compile(
    r"(?:출신|데뷔\s+이후|활동\s+이후)[^.!?。！？]{0,180}?"
    r"(?:가수|배우|연기자|방송인)[^.!?。！？]{0,180}?"
    r"(?:활동\s+분야|활동\s+영역|분야|영역)[^.!?。！？]{0,80}?"
    r"(?:넓혀왔다|넓혀\s+왔다|확장해왔다|확장해\s+왔다)$"
)
_PRIMARY_INSTITUTIONAL_PROCEDURE_RE = re.compile(
    r"(?:회의|위원회|금통위|금융통화위원회)[^.!?。！？]{0,180}?"
    r"(?:열리기|개최되기)\s+전에[^.!?。！？]{0,220}?"
    r"(?:기간|절차|관행)(?:을|를)?\s+(?:가진다|둔다|운영한다|갖는다)$"
)
_PRIMARY_CAUSAL_ANALYSIS_RE = re.compile(
    r"(?:영향|요인|배경|원인)(?:으)?로\s+"
    r"(?:분석했|해석했|진단했)(?:다|습니다)$"
)
_ATTRIBUTED_FORECAST_ACTOR_RE = re.compile(
    r"^[^.!?。！？]{1,80}?(?:은|는|이|가)\s+[^.!?。！？]{0,180}?"
    r"(?:전망했다|예상했다|내다봤다)"
)
_FORECAST_SURFACE_RE = re.compile(
    r"(?:전망됐|전망된다|전망됩니다|예상됐|예상된다|예상됩니다|유력시된다|유력하다|"
    r"가능성(?:은|이)\s*(?:낮|높)(?:다|습니다)|판단이\s*우세(?:하다|합니다)|"
    r"시장\s+무게중심[^.!?。！？]{0,80}?기울고\s+있다|"
    r"전망(?:은|이|도)\s+[^.!?。！？]{0,140}?(?:강화|끌어올|압박|작용|영향을\s+미치)"
    r"[^.!?。！？]{0,60}?(?:있다|있습니다|한다|합니다|했다|했습니다))"
)
_FORECAST_EXPLICIT_ATTRIBUTION_CUES = (
    "에 따르면",
    "보고서에서",
    "보고서는",
    "조사에서",
    "조사에서는",
    "설문에서",
    "설문에서는",
)
_CURRENT_EVENT_BEFORE_OUTLOOK_CUES = (
    "돌파한",
    "넘어선",
    "넘었다",
    "기록한",
    "마감한",
    "상승한",
    "하락한",
    "증가한",
    "감소한",
)
_STALE_DAY_COMPLETED_EVENT_ALIASES = (
    ("운영했다", "진행했다"),
    ("운영하였다", "진행했다"),
    ("실시했다", "진행했다"),
    ("실시하였다", "진행했다"),
    ("제외했다", "진행했다"),
    ("제외하였다", "진행했다"),
    ("말소했다", "진행했다"),
    ("등록했다", "진행했다"),
)
_SAME_YEAR_EXPLICIT_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})년\s*(1[0-2]|0?[1-9])월\s*([0-2]?\d|3[01])일"
)
_SAME_YEAR_DATED_EVENT_CUES = (
    "인수",
    "낙찰",
    "매각",
    "체결",
    "발표",
    "출시",
    "발매",
    "공개",
    "진행",
    "개최",
    "선정",
    "수주",
    "투자",
    "확정",
    "결정",
    "승리",
    "패배",
    "기록",
    "인상",
    "인하",
    "동결",
    "상승",
    "하락",
)
_EXPLICIT_DAY_RE = re.compile(r"(?<!\d)(?:[0-2]?\d|3[01])일")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def _primary_sentence(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""
    for sentence in _SENTENCE_SPLIT_RE.split(normalized):
        sentence = sentence.strip()
        if sentence:
            return sentence
    return normalized


def _sentences(value: str) -> tuple[str, ...]:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ()
    return tuple(
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(normalized)
        if sentence.strip()
    )


def _has_primary_current_event(value: str) -> bool:
    return any(cue in value for cue in _PRIMARY_CURRENT_EVENT_CUES)


def _primary_attributed_forecast(value: str) -> bool:
    normalized = value.rstrip(".!?。！？").rstrip()
    if _ATTRIBUTED_FORECAST_ACTOR_RE.search(normalized) is not None:
        return True
    return (
        any(cue in normalized for cue in ("조사에서", "설문에서", "보고서에서"))
        and any(cue in normalized for cue in ("응답", "전망", "예상"))
    )


def _primary_non_event_state(value: str) -> bool:
    normalized = _primary_sentence(value).rstrip(".!?。！？").rstrip()
    if not normalized:
        return False
    # These are proposition types, so they outrank incidental event words inside
    # subordinate/background phrases such as `계약 체결 후 ... 충족해야 한다`.
    if _PRIMARY_GOAL_RE.search(normalized) is not None:
        return True
    if normalized.endswith(_PRIMARY_NORMATIVE_ENDINGS):
        return True
    if _PRIMARY_KBO_TEAM_PARTICIPATION_RE.search(normalized) is not None:
        return True
    if (
        _PRIMARY_MARKET_ATTENTION_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_POLICY_COMMENTARY_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        any(cue in normalized for cue in _PRIMARY_STATIC_RULE_CUES)
        and normalized.endswith(_PRIMARY_STATIC_RULE_ENDINGS)
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_STATIC_ASSET_CLASSIFICATION_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_AI_TREND_STRATEGY_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_PROMOTIONAL_ROLLUP_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_PROMOTIONAL_TRAINING_BENEFIT_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_GENERIC_COMPONENT_SECTION_RE.search(normalized) is not None
        and normalized.endswith(("구성했다", "구성하였다"))
    ):
        return True
    if (
        normalized.endswith(_PRIMARY_COMPONENT_ENDINGS)
        and any(cue in normalized for cue in _PRIMARY_COMPONENT_CONTAINER_CUES)
    ):
        return True
    if normalized.endswith(_PRIMARY_METHOD_ENDINGS):
        return True
    if normalized.endswith(_PRIMARY_ABSENCE_STATE_ENDINGS):
        return True
    if _PRIMARY_REFERENTIAL_PLAN_RE.search(normalized) is not None:
        return True
    if (
        _PRIMARY_INTENDED_USE_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if _PRIMARY_UNATTRIBUTED_STATE_RE.search(normalized) is not None:
        return True
    if (
        _PRIMARY_PERFORMANCE_EVALUATION_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if _PRIMARY_CAREER_HISTORY_RE.search(normalized) is not None:
        return True
    if (
        _PRIMARY_INSTITUTIONAL_PROCEDURE_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if (
        _PRIMARY_CAUSAL_ANALYSIS_RE.search(normalized) is not None
        and _EXPLICIT_DAY_RE.search(normalized) is None
    ):
        return True
    if any(cue in normalized for cue in _PRIMARY_ANALYTICAL_CUES):
        return True
    if normalized.endswith(_PRIMARY_RESPONSE_ENDINGS) and any(
        cue in normalized for cue in _PRIMARY_ABSTRACT_RESPONSE_CUES
    ):
        return True
    if _has_primary_current_event(normalized):
        return False
    return False


def _forecast_has_current_event_before_outlook(sentence: str) -> bool:
    if "가운데" not in sentence:
        return False
    prefix = sentence.split("가운데", 1)[0]
    return any(char.isdigit() for char in prefix) and any(
        cue in prefix for cue in _CURRENT_EVENT_BEFORE_OUTLOOK_CUES
    )


def _forecast_sentence_attributed(sentence: str) -> bool:
    if any(cue in sentence for cue in _FORECAST_EXPLICIT_ATTRIBUTION_CUES):
        return True
    if _ATTRIBUTED_FORECAST_ACTOR_RE.search(sentence.rstrip(".!?。！？").rstrip()) is not None:
        return True
    if (
        "%" in sentence
        and any(cue in sentence for cue in ("응답자", "조사", "설문"))
    ):
        return True
    return _forecast_has_current_event_before_outlook(sentence)


def unattributed_forecast_text(value: str) -> bool:
    """Return true when a visible outlook/consensus claim has no visible source.

    A quantified current event may carry a subordinate outlook in the same
    proposition (for example, debt crossing a measured threshold followed by a
    consequence outlook). Prospective concrete events such as announced releases
    are outside this detector.
    """
    for sentence in _sentences(value):
        if _FORECAST_SURFACE_RE.search(sentence) is None:
            continue
        if not _forecast_sentence_attributed(sentence):
            return True
    return False


def context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    if _core_context_dependent_summary(normalized):
        return True
    if any(normalized.startswith(cue) for cue in _CONTEXTUAL_LIST_LEADS):
        return True
    return _REFERENTIAL_CONTENT_LEAD_RE.search(normalized) is not None


def metadata_or_caption_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    return (
        _core_metadata_or_caption_text(value)
        or _TRAILING_DATELINE_BYLINE_RE.search(normalized) is not None
        or _LEADING_DATELINE_BYLINE_RE.search(normalized) is not None
    )


def visible_metadata_text(value: str) -> bool:
    return metadata_or_caption_text(value)


def _current_week_aggregate(value: str) -> bool:
    normalized = " ".join(value.split())
    if not re.search(r"지난\s*주(?:\([^)]{1,40}\))?", normalized):
        return False
    return any(cue in normalized for cue in _CURRENT_WEEK_AGGREGATE_CUES)


def _prior_period_policy_event(value: str) -> bool:
    # Decimal points are numeric punctuation, not sentence boundaries. Removing
    # only digit-to-digit dots lets the detector see `2.50% -> 2.75%` without
    # allowing a match to cross an actual sentence stop.
    normalized = " ".join(value.split())
    decimal_normalized = re.sub(r"(?<=\d)\.(?=\d)", "", normalized)
    return _PRIOR_PERIOD_POLICY_EVENT_RE.search(decimal_normalized) is not None


def stale_explicit_past_event_text(value: str, *, now: datetime | None = None) -> bool:
    primary = _primary_sentence(value)
    if _core_stale_explicit_past_event_text(primary, now=now):
        return True
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for match in _SAME_YEAR_EXPLICIT_DATE_RE.finditer(primary):
        year, month, day = (int(item) for item in match.groups())
        try:
            candidate = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        age = reference - candidate
        if age <= timedelta(hours=72) or candidate > reference + timedelta(hours=6):
            continue
        event_surface = primary[match.end() : match.end() + 180]
        if any(cue in event_surface for cue in _SAME_YEAR_DATED_EVENT_CUES):
            return True
    return False


def stale_relative_past_event_text(value: str) -> bool:
    return _core_stale_relative_past_event_text(_primary_sentence(value))


def stale_relative_period_event_text(value: str) -> bool:
    normalized = _primary_sentence(value)
    # `지난 주말` is one relative-weekend expression. The core pattern's `지난 주`
    # prefix must not reinterpret it as a completed stale week.
    if "지난 주말" in normalized or "지난주말" in normalized:
        return False
    # A fresh article may report a newly computed aggregate over the immediately
    # preceding week. The measurement/report is current even though its window is
    # named `지난주`.
    if _current_week_aggregate(normalized):
        return False
    # Conversely, a prior-period policy action is stale background when the
    # primary visible proposition itself is the old action. Include transitive
    # `올렸다` / `내렸다`, which the original market-price cue set omitted.
    if _prior_period_policy_event(normalized):
        return True
    return _core_stale_relative_period_event_text(normalized)


def stale_day_only_context(value: str, *, now: datetime | None = None) -> bool:
    primary = _primary_sentence(value)
    if _core_stale_day_only_context(primary, now=now):
        return True
    normalized_alias = re.sub(r"경기\s*,\s*", "경기에서 ", primary)
    normalized_alias = normalized_alias.replace("경기 중", "경기에서")
    for source, target in _STALE_DAY_COMPLETED_EVENT_ALIASES:
        normalized_alias = normalized_alias.replace(source, target)
    if normalized_alias == primary:
        return False
    return _core_stale_day_only_context(normalized_alias, now=now)


def stale_quarter_context(value: str, *, now: datetime | None = None) -> bool:
    return _core_stale_quarter_context(_primary_sentence(value), now=now)


def non_event_analytical_text(value: str) -> bool:
    # Preserve the established whole-card detector. Only a visibly attributed
    # forecast/reporting proposition may keep later descriptive background from
    # turning the whole card into a non-event; generic claims or abstract
    # analysis are never rescued merely because they end with `밝혔다/분석했다`.
    primary = _primary_sentence(value)
    primary_non_event = _primary_non_event_state(primary)
    if unattributed_forecast_text(value):
        return True
    core_non_event = _core_non_event_analytical_text(value)
    if core_non_event and _primary_attributed_forecast(primary) and not primary_non_event:
        return False
    return core_non_event or primary_non_event


def publisher_notice_boilerplate(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        any(cue in normalized for cue in _PUBLISHER_NOTICE_PERMISSION_CUES)
        and sum(term in normalized for term in _PUBLISHER_NOTICE_RESTRICTION_TERMS) >= 2
        and any(cue in normalized for cue in _PUBLISHER_NOTICE_LEGAL_CUES)
    )


def standalone_sports_photo_caption(value: str) -> bool:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 180:
        return False
    if sum(normalized.count(mark) for mark in ".!?。！？") > 1:
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if (
        not any(cue in normalized for cue in _SPORTS_DEPICTIVE_ACTION_CUES)
        and _SPORTS_DEPICTIVE_ACTION_RE.search(normalized) is None
    ):
        return False
    return normalized.endswith(_SPORTS_DEPICTIVE_ENDINGS)
