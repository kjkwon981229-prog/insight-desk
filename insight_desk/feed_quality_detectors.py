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


def _orphaned_referential_event(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return _ORPHANED_REFERENTIAL_EVENT_RE.search(normalized) is not None


def _orphaned_visible_actor(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _GENERIC_LABOR_MANAGEMENT_RE.search(normalized) is not None
        or _REFERENTIAL_REPORT_LEAD_RE.search(normalized) is not None
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
        or _unidentified_kbo_result(normalized)
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
    )
