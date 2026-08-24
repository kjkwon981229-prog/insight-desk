from __future__ import annotations

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
)
_CONTEXT_DEPENDENT_SUMMARY_PHRASES = ("이번 상황",)
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
    r"^(?:지난\s+)?\d{1,2}일\s+[^,.]{0,60}?(?:경기|전)에서\s+\d+\s*(?:타수|이닝|분|경기)\b"
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
)
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
_EXPLANATORY_STATE_NOUN_CUES = ("원인", "배경", "힘", "요인", "영향")
_EXPLANATORY_STATE_ENDINGS = (
    "두드러지고 있다",
    "두드러지고 있습니다",
    "두드러진다",
    "작용하고 있다",
    "작용하고 있습니다",
    "작용한다",
    "영향을 미치고 있다",
    "영향을 미치고 있습니다",
    "영향을 미친다",
    "배경이다",
    "배경으로 꼽힌다",
    "요인이다",
    "요인으로 꼽힌다",
    "원인이다",
    "원인으로 꼽힌다",
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
    CONTEXT_DEPENDENT_SUMMARY = "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"
    NON_EVENT_ANALYTICAL_SUMMARY = "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"
    CONDITIONAL_ANALYTICAL_SUMMARY = "FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY"


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


def context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    if any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_SUMMARY_LEADS):
        return True
    if any(phrase in normalized for phrase in _CONTEXT_DEPENDENT_SUMMARY_PHRASES):
        return True
    if _BARE_ANNIVERSARY_LEAD_RE.search(normalized) is not None:
        return True
    if _DATE_LED_SUBJECTLESS_SPORTS_RESULT_RE.search(normalized) is not None:
        return True
    return _bare_ranking_fragment(normalized)


def non_event_analytical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    if normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS):
        return True
    if normalized.endswith(_NON_EVENT_ATTENTION_ENDINGS):
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
    del topic, headline
    issues: list[VisibleStoryIssue] = []
    if context_dependent_summary(summary):
        issues.append(VisibleStoryIssue.CONTEXT_DEPENDENT_SUMMARY)
    if non_event_analytical_text(summary):
        issues.append(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY)
    if conditional_analytical_text(summary):
        issues.append(VisibleStoryIssue.CONDITIONAL_ANALYTICAL_SUMMARY)
    return tuple(issues)
