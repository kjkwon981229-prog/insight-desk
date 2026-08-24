from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
import re


_CONTEXT_DEPENDENT_SUMMARY_LEADS = (
    "여기에 ",
    "여기에,",
    "이후 ",
    "이 딜러는 ",
    "이번 ",
    "팬들의 ",
    "그는 ",
    "그가 ",
    "그녀는 ",
    "그녀가 ",
    "이들은 ",
    "이들이 ",
    "가운데 ",
    "가운데,",
)
_CONTEXT_DEPENDENT_SUMMARY_PHRASES = ("이번 상황",)
_GENERIC_CONTEXT_SUBJECT_RE = re.compile(
    r"^(?:(?:이|해당)\s*)?(?:회사|기업|업체)(?:는|은|이|가|\s+측은|\s+측이)(?:\s|$)"
    r"|^(?:(?:두|세|네)\s+)?(?:투수|선수|타자|팀)(?:는|은|이|가)?(?:\s|$)"
)
_REFERENTIAL_EVENT_RE = re.compile(
    r"(?:^|\s)이번\s+(?:승리|패배|경기|장면|계약|발표|결정|조치|상황)"
)
_BARE_ANNIVERSARY_LEAD_RE = re.compile(r"^데뷔\s+\d+\s*주년을\s+맞은\s+가운데(?:\s|$)")
_BARE_RANKING_CUES = ("최고의 루키",)
_BARE_RANKING_CONTEXT_TERMS = (
    "K탑스타",
    "KTOPSTAR",
    "투표",
    "랭킹",
    "차트",
    "부문",
    "시상식",
    "어워드",
    "수상",
)
_DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE = re.compile(
    r"^(?:지난\s+)?\d{1,2}일\s+[^,.]{0,60}?(?:경기|전)에서\s+"
    r"[^,.]{0,60}?\d+\s*(?:타수|이닝|분|경기)\b"
)
_CONTEXT_DEPENDENT_CREATED_CATEGORY_RE = re.compile(
    r"(?:분야|부문)(?:를|을)?\s+(?:신설(?:했|한|한다|됐다|된|된다)?|새로\s+마련)"
)
_CREATED_CATEGORY_PARENT_CUES = (
    "공모전",
    "공모",
    "경진대회",
    "디자인 대전",
    "시상식",
    "프로그램",
    "프로젝트",
    "사업",
    "제도",
    "과정",
    "학과",
    "전형",
    "조직",
    "본부",
    "센터",
)
_MISSING_FINANCIAL_TENOR_RE = re.compile(
    r"(?:미국|한국|일본|중국|독일|영국)\s+년\s+만기\s+(?:국채|채권)"
)
_MISSING_FINANCIAL_VALUE_RE = re.compile(
    r"(?:금리|수익률|환율|가격|지수|비율)(?:이|가|은|는)\s+(?:에|로)\s+"
    r"(?:도달|진입|마감|상승|하락|올랐|내렸)"
)
_INCOMPLETE_ADNOMINAL_HEADLINE_RE = re.compile(
    r"(?:이끈|거둔|밝힌|발표한|체결한|개최한|진행한|기록한|수주한|선정된|확정된|"
    r"결정된|출시한|발매한|공개한|상승한|하락한|오른|내린|앞둔|나선|보인|만든|"
    r"올린|늘린|줄인|마련한|추진한|허용한)$"
)
_VISIBLE_BYLINE_RE = re.compile(
    r"^[\(（\[][^\)）\]]{0,80}(?:기자|특파원|뉴스)[\)）\]]\s*"
)
_DISCOURSE_LEADS = ("하지만 ", "그러나 ", "다만 ", "반면 ")
_DAY_ONLY_PAST_RE = re.compile(r"(?:^|[,.]\s*|\s)지난\s+([0-3]?\d)일(?:\s|$)")
_STALE_DAY_ONLY_EVENT_CUES = (
    "경기",
    "전에서",
    "등판",
    "진행",
    "개최",
    "발표",
    "출시",
    "공개",
    "체결",
    "기록",
    "승리",
    "패배",
)
_NON_EVENT_ANALYTICAL_ENDINGS = (
    "설명하기 어렵다",
    "설명하기 힘들다",
    "것으로 보인다",
    "것으로 보입니다",
    "것으로 풀이된다",
    "것으로 풀이됩니다",
)
_NON_EVENT_ATTENTION_ENDINGS = (
    "관심이 쏠리고 있다",
    "관심이 쏠리고 있습니다",
    "관심이 모이고 있다",
    "관심이 모이고 있습니다",
    "주목을 받고 있다",
    "주목받고 있다",
    "가능성을 주목하고 있다",
    "가능성을 주목하고 있습니다",
)
_NON_EVENT_INFERENCE_ENDINGS = ("셈이다", "셈입니다")
_EVALUATIVE_CONDITION_MARKERS = ("해야", "돼야", "되어야")
_EVALUATIVE_CONDITION_ENDINGS = (
    "가능하다고 봤다",
    "필요하다고 봤다",
    "가능하다고 평가했다",
    "필요하다고 평가했다",
    "의미가 있다고 봤다",
)
_DESCRIPTIVE_ATTRIBUTE_CUES = (
    "장르",
    "사운드",
    "스타일",
    "분위기",
    "매력",
    "탑라인",
    "트랙",
    "색채",
    "특징",
)
_DESCRIPTIVE_PREDICATE_CUES = (
    "대비를 이루",
    "은유한다",
    "표현한다",
    "보여준다",
    "담아낸다",
    "결합한",
    "특징이다",
)
_EXPLANATORY_STATE_NOUN_CUES = ("원인", "배경", "힘", "요인", "영향", "신호")
_EXPLANATORY_STATE_ENDINGS = (
    "두드러지고 있다",
    "두드러지고 있습니다",
    "두드러진다",
    "작용하고 있다",
    "작용하고 있습니다",
    "작용한다",
    "작용할 수 있다",
    "작용할 수 있습니다",
    "영향을 미치고 있다",
    "영향을 미치고 있습니다",
    "영향을 미친다",
    "영향을 미칠 수 있다",
    "영향을 미칠 수 있습니다",
    "배경이다",
    "배경으로 꼽힌다",
    "요인이다",
    "요인으로 꼽힌다",
    "원인이다",
    "원인으로 꼽힌다",
    "영향으로 해석된다",
    "영향으로 해석됩니다",
    "영향으로 분석된다",
    "영향으로 분석됩니다",
    "배경으로 해석된다",
    "배경으로 해석됩니다",
    "요인으로 해석된다",
    "요인으로 해석됩니다",
    "원인으로 해석된다",
    "원인으로 해석됩니다",
)
_CONCRETE_EVENT_PREDICATE_CUES = (
    "발매했다",
    "공개했다",
    "개최했다",
    "출시했다",
    "체결했다",
    "수주했다",
    "선정됐다",
    "수상했다",
    "승리했다",
    "발표했다",
    "밝혔다",
    "확정했다",
    "결정했다",
    "도입했다",
    "시행했다",
    "데뷔했다",
    "마감했다",
    "상승했다",
    "하락했다",
    "올랐다",
    "내렸다",
    "동결했다",
    "인상했다",
    "인하했다",
    "기록했다",
)
_CONDITIONAL_EVENT_CUES = (
    "발표",
    "밝혔다",
    "결정",
    "도입",
    "시행",
    "공개",
    "추진",
    "합의",
    "체결",
    "승인",
    "확정",
)
_CONDITIONAL_SCENARIO_RE = re.compile(r"\s(?:경우|시)\s")
_SENTENCE_TERMINALS = ".!?。！？"


class VisibleStoryIssue(StrEnum):
    CONTEXT_DEPENDENT_HEADLINE = "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE"
    CONTEXT_DEPENDENT_SUMMARY = "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"
    HEADLINE_SUMMARY_COLLISION = "FEED_QUALITY_HEADLINE_SUMMARY_COLLISION"
    VISIBLE_METADATA = "FEED_QUALITY_VISIBLE_METADATA"
    NON_EVENT_ANALYTICAL_SUMMARY = "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"
    CONDITIONAL_ANALYTICAL_SUMMARY = "FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY"
    MALFORMED_VISIBLE_TEXT = "FEED_QUALITY_MALFORMED_VISIBLE_TEXT"


def _bare_ranking_fragment(value: str) -> bool:
    normalized = " ".join(value.split())
    has_bare_ranking = (
        any(cue in normalized for cue in _BARE_RANKING_CUES)
        or re.search(r"\d+\s*주\s*연속\s*1위", normalized) is not None
    )
    if not has_bare_ranking:
        return False
    folded = normalized.casefold()
    return not any(term.casefold() in folded for term in _BARE_RANKING_CONTEXT_TERMS)


def _context_dependent_text(value: str) -> bool:
    normalized = " ".join(value.split())
    if any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_SUMMARY_LEADS):
        return True
    if any(phrase in normalized for phrase in _CONTEXT_DEPENDENT_SUMMARY_PHRASES):
        return True
    if _GENERIC_CONTEXT_SUBJECT_RE.search(normalized) is not None:
        return True
    if _REFERENTIAL_EVENT_RE.search(normalized) is not None:
        return True
    if _BARE_ANNIVERSARY_LEAD_RE.search(normalized) is not None:
        return True
    if _DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE.search(normalized) is not None:
        return True
    if (
        _CONTEXT_DEPENDENT_CREATED_CATEGORY_RE.search(normalized) is not None
        and not any(cue in normalized for cue in _CREATED_CATEGORY_PARENT_CUES)
    ):
        return True
    return _bare_ranking_fragment(normalized)


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split())
    return (
        _MISSING_FINANCIAL_TENOR_RE.search(normalized) is not None
        or _MISSING_FINANCIAL_VALUE_RE.search(normalized) is not None
    )


def context_dependent_headline(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    return (
        _context_dependent_text(normalized)
        or _INCOMPLETE_ADNOMINAL_HEADLINE_RE.search(normalized) is not None
    )


def context_dependent_summary(value: str) -> bool:
    return _context_dependent_text(value)


def visible_metadata_text(value: str) -> bool:
    return _VISIBLE_BYLINE_RE.search(" ".join(value.split())) is not None


def _visible_identity(value: str) -> str:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    for cue in _DISCOURSE_LEADS:
        if normalized.startswith(cue):
            normalized = normalized[len(cue) :].lstrip()
            break
    return normalized.casefold()


def headline_summary_collision(*, headline: str, summary: str) -> bool:
    return bool(_visible_identity(headline)) and _visible_identity(headline) == _visible_identity(summary)


def stale_day_only_context(value: str, *, now: datetime | None = None) -> bool:
    normalized = " ".join(value.split())
    if any(cue in normalized for cue in ("오늘", "현재", "최근")):
        return False
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for match in _DAY_ONLY_PAST_RE.finditer(normalized):
        day = int(match.group(1))
        candidates: list[datetime] = []
        for month_offset in (0, -1):
            month_index = reference.year * 12 + reference.month - 1 + month_offset
            year, zero_based_month = divmod(month_index, 12)
            try:
                candidate = datetime(year, zero_based_month + 1, day, tzinfo=timezone.utc)
            except ValueError:
                continue
            if candidate <= reference + timedelta(hours=6):
                candidates.append(candidate)
        if not candidates or reference - max(candidates) <= timedelta(hours=72):
            continue
        tail = normalized[match.end() : match.end() + 100]
        if any(cue in tail for cue in _STALE_DAY_ONLY_EVENT_CUES):
            return True
    return False


def non_event_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    if normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS):
        return True
    if normalized.endswith(_NON_EVENT_ATTENTION_ENDINGS):
        return True
    if (
        normalized.endswith(_NON_EVENT_INFERENCE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    if (
        any(marker in normalized for marker in _EVALUATIVE_CONDITION_MARKERS)
        and normalized.endswith(_EVALUATIVE_CONDITION_ENDINGS)
    ):
        return True
    if (
        any(cue in normalized for cue in _EXPLANATORY_STATE_NOUN_CUES)
        and normalized.endswith(_EXPLANATORY_STATE_ENDINGS)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    ):
        return True
    return (
        any(cue in normalized for cue in _DESCRIPTIVE_ATTRIBUTE_CUES)
        and any(cue in normalized for cue in _DESCRIPTIVE_PREDICATE_CUES)
        and not any(cue in normalized for cue in _CONCRETE_EVENT_PREDICATE_CUES)
    )


def conditional_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split())
    has_reporting_event = any(cue in normalized for cue in _CONDITIONAL_EVENT_CUES)
    if "더라도" in normalized and "이어야" in normalized:
        return not has_reporting_event
    if _CONDITIONAL_SCENARIO_RE.search(normalized) is None:
        return False
    return not has_reporting_event


def visible_story_issues(
    *,
    topic: str,
    headline: str,
    summary: str,
) -> tuple[VisibleStoryIssue, ...]:
    del topic
    issues: list[VisibleStoryIssue] = []
    if context_dependent_headline(headline):
        issues.append(VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE)
    if context_dependent_summary(summary):
        issues.append(VisibleStoryIssue.CONTEXT_DEPENDENT_SUMMARY)
    if headline_summary_collision(headline=headline, summary=summary):
        issues.append(VisibleStoryIssue.HEADLINE_SUMMARY_COLLISION)
    if visible_metadata_text(headline) or visible_metadata_text(summary):
        issues.append(VisibleStoryIssue.VISIBLE_METADATA)
    if non_event_analytical_text(summary):
        issues.append(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY)
    if conditional_analytical_text(summary):
        issues.append(VisibleStoryIssue.CONDITIONAL_ANALYTICAL_SUMMARY)
    if malformed_visible_text(headline) or malformed_visible_text(summary):
        issues.append(VisibleStoryIssue.MALFORMED_VISIBLE_TEXT)
    return tuple(issues)
