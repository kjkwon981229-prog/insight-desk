from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re

from insight_desk import feed_quality_detectors as detectors


class StoryAdmissionStage(StrEnum):
    MATERIAL = "material"
    VISIBLE = "visible"


class StoryAdmissionReason(StrEnum):
    STANDALONE_COMPLETENESS = "STANDALONE_COMPLETENESS"
    NON_EVENT_DESCRIPTION = "NON_EVENT_DESCRIPTION"
    TOPIC_OWNERSHIP = "TOPIC_OWNERSHIP"
    FRESHNESS = "FRESHNESS"
    EVENT_CENTRALITY = "EVENT_CENTRALITY"
    METADATA = "METADATA"
    MALFORMED = "MALFORMED"
    MIXED_BINDING = "MIXED_BINDING"
    BIOGRAPHY = "BIOGRAPHY"
    FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED = (
        "FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED"
    )


@dataclass(frozen=True, slots=True)
class StoryAdmissionInput:
    stage: StoryAdmissionStage = StoryAdmissionStage.VISIBLE
    topic: str = ""
    headline: str = ""
    summary: str = ""
    source_text: str = ""
    subject: str = ""
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class StoryAdmissionDecision:
    stage: StoryAdmissionStage
    accepted: bool
    reasons: tuple[StoryAdmissionReason, ...]
    compatibility_codes: tuple[str, ...] = ()


_KBO_TOPIC_NAMES = frozenset({"KBO·한화 이글스", "kbo_hanwha"})
_KPOP_TOPIC_NAMES = frozenset({"엔터·음악·K-POP", "kpop"})
_KBO_ENTERTAINMENT_ENTITY_CUES = ("그룹", "아이돌", "멤버", "가수", "배우")
_KBO_ENTERTAINMENT_ACTION_CUES = ("승리 요정", "시구", "시타")
_KBO_BASEBALL_EVENT_CUES = (
    "경기",
    "승리",
    "패배",
    "순위",
    "홈런",
    "투수",
    "타자",
    "이닝",
    "세이브",
    "홀드",
    "등판",
    "선발",
    "트레이드",
    "부상",
    "관중",
    "경기 시간",
    "KBO",
    "프로야구",
    "퓨처스리그",
    "기록",
)
_KBO_NON_BASEBALL_PARTNERSHIP_CUES = (
    "의료지원",
    "협력병원",
    "한의치료",
    "병원",
)
_KBO_RANK_CUES = ("순위", "리그 1위", "리그 2위", "리그 3위", "리그 4위", "리그 5위")
_HANWHA_OPPONENT_RE = re.compile(
    r"한화(?:\s+이글스)?(?:전|와의\s+경기|와\s+경기|와의\s+맞대결)"
)
_KPOP_HEADLINE_SCOPE_CUES = (
    "K-POP",
    "케이팝",
    "가수",
    "그룹",
    "아이돌",
    "앨범",
    "음원",
    "차트",
    "음악",
    "뮤직",
    "음반",
    "컴백",
    "데뷔",
    "콘서트",
    "공연",
    "무대",
    "수상",
    "빌보드",
    "Billboard",
    "EP",
    "싱글",
    "쇼케이스",
)
_BIO_IDENTITY_CUES = ("출신", "가수이자", "배우인", "멤버인", "소속된", "소속돼")
_BIO_ROLE_CUES = ("메인댄서", "리드래퍼", "서브보컬", "리더", "보컬", "래퍼", "역할")
_BIO_STATE_ENDINGS = (
    "담당하고 있다",
    "담당하고 있습니다",
    "맡고 있다",
    "맡고 있습니다",
    "활동하고 있다",
    "활동하고 있습니다",
    "소속돼 있다",
    "소속돼 있습니다",
    "소속되어 있다",
    "소속되어 있습니다",
)
_BIO_COMPOSITION_CUES = ("구성된", "구성돼", "구성되어", "인조", "멤버로 구성")
_BIO_REPUTATION_CUES = ("글로벌 인기", "인기를 얻", "대표하는", "대표 팀", "대표 그룹", "자리매김")
_SPORTS_CONTEXT_CUES = ("경기에서", "전에서", "경기 중", "경기에")
_STALE_SPORTS_RETROSPECTIVE_ENDINGS = ("나왔다", "벌어졌다", "기록됐다", "기록되었다")
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})년")
_RELATIVE_PAST_EVENT_RE = re.compile(r"(?:지난달|지난\s+달|지난주|지난\s+주|지난\s+분기|지난\s+연도)")
_RELATIVE_PAST_EVENT_PREDICATE_RE = re.compile(
    r"(?:올렸|내렸|인상했|인하했|동결했|발표했|공개했|출시했|발매했|개최했|"
    r"체결했|수주했|선정됐|수상했|승리했|패했|기록했|도달했|진입했|투입했|가동했)"
)
_BARE_FORECAST_END_RE = re.compile(
    r"(?:유력시된다|유력하다|유력합니다|전망된다|전망됩니다|예상된다|예상됩니다)$"
)
_FORECAST_ATTRIBUTION_CUES = (
    "에 따르면",
    "은 전망",
    "는 전망",
    "이 전망",
    "가 전망",
    "전망했다",
    "예상했다",
    "내다봤다",
    "밝혔다",
    "분석했다",
)


_FQ_CONTEXT_HEADLINE = detectors.VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE.value
_FQ_CONTEXT_SUMMARY = detectors.VisibleStoryIssue.CONTEXT_DEPENDENT_SUMMARY.value
_FQ_COLLISION = detectors.VisibleStoryIssue.HEADLINE_SUMMARY_COLLISION.value
_FQ_METADATA = detectors.VisibleStoryIssue.VISIBLE_METADATA.value
_FQ_NON_EVENT = detectors.VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY.value
_FQ_CONDITIONAL = detectors.VisibleStoryIssue.CONDITIONAL_ANALYTICAL_SUMMARY.value
_FQ_MALFORMED = detectors.VisibleStoryIssue.MALFORMED_VISIBLE_TEXT.value
_FQ_MIXED = detectors.VisibleStoryIssue.MIXED_EVENT_SUMMARY.value
_FQ_STALE = detectors.VisibleStoryIssue.STALE_DATED_CONTEXT.value
_FQ_TOPIC = detectors.VisibleStoryIssue.TOPIC_BINDING.value
_FQ_STALE_SPORTS = "FEED_QUALITY_STALE_SPORTS_RETROSPECTIVE"

_MATERIAL_CONTEXT = "MATERIAL_CONTEXT_DEPENDENT_FRAGMENT"
_MATERIAL_NON_EVENT = "MATERIAL_NON_EVENT_ANALYTICAL_JUDGMENT"
_MATERIAL_CONDITIONAL = "MATERIAL_CONDITIONAL_ANALYTICAL_SCENARIO"
_MATERIAL_STALE_EXPLICIT = "MATERIAL_STALE_EXPLICIT_PAST_EVENT"
_MATERIAL_STALE_DATED = "MATERIAL_STALE_DATED_CONTEXT"
_MATERIAL_STALE_SPORTS = "MATERIAL_STALE_SPORTS_RETROSPECTIVE"


def _dedupe(values):
    return tuple(dict.fromkeys(values))


def _biographical_text(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if (
        any(cue in normalized for cue in _BIO_IDENTITY_CUES)
        and any(cue in normalized for cue in _BIO_ROLE_CUES)
        and normalized.endswith(_BIO_STATE_ENDINGS)
    ):
        return True
    return (
        any(cue in normalized for cue in _BIO_COMPOSITION_CUES)
        and any(cue in normalized for cue in _BIO_REPUTATION_CUES)
    )


def _stale_sports_retrospective(value: str, *, now: datetime) -> bool:
    normalized = " ".join(value.split())
    years = [int(item) for item in _YEAR_RE.findall(normalized)]
    if not years or not any(year < now.year for year in years):
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if "장면" not in normalized and "기록" not in normalized:
        return False
    terminal = normalized.rstrip(".!?。！？").rstrip()
    return terminal.endswith(_STALE_SPORTS_RETROSPECTIVE_ENDINGS)


def _stale_relative_material_event(value: str) -> bool:
    normalized = " ".join(value.split())
    match = _RELATIVE_PAST_EVENT_RE.search(normalized)
    if match is None:
        return False
    tail = normalized[match.end() :]
    return _RELATIVE_PAST_EVENT_PREDICATE_RE.search(tail) is not None


def _bare_unattributed_forecast(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if len(normalized) > 90 or _BARE_FORECAST_END_RE.search(normalized) is None:
        return False
    if any(cue in normalized for cue in _FORECAST_ATTRIBUTION_CUES):
        return False
    # A measured current event plus a forecast is not a bare forecast card.
    if re.search(r"\d[\d,.]*\s*(?:%|％|원|조\s*원|억\s*원|명|건|개|배)", normalized):
        return False
    return True


def _kbo_topic_ownership_violation(headline: str, summary: str) -> bool:
    combined = " ".join(f"{headline} {summary}".split())
    if detectors.kbo_hanwha_comparison_only(
        topic="KBO·한화 이글스", headline=headline, summary=summary
    ):
        return True
    if (
        any(cue in combined for cue in _KBO_ENTERTAINMENT_ENTITY_CUES)
        and any(cue in combined for cue in _KBO_ENTERTAINMENT_ACTION_CUES)
    ):
        return True
    if (
        any(cue in combined for cue in _KBO_NON_BASEBALL_PARTNERSHIP_CUES)
        and not any(cue in combined for cue in _KBO_BASEBALL_EVENT_CUES)
    ):
        return True
    if _HANWHA_OPPONENT_RE.search(combined) is not None and any(
        cue in combined for cue in _KBO_RANK_CUES
    ):
        lead = headline.split(",", 1)[0].strip()
        if "한화" not in lead:
            return True
    return False


def _kpop_topic_ownership_violation(headline: str) -> bool:
    folded = headline.casefold()
    return not any(cue.casefold() in folded for cue in _KPOP_HEADLINE_SCOPE_CUES)


def _freshness_codes(value: str, *, now: datetime) -> tuple[bool, tuple[str, ...]]:
    if _stale_sports_retrospective(value, now=now):
        return True, (_FQ_STALE_SPORTS, _MATERIAL_STALE_SPORTS)
    if (
        detectors.stale_explicit_past_event_text(value, now=now)
        or detectors.stale_relative_past_event_text(value)
        or detectors.stale_relative_period_event_text(value)
        or _stale_relative_material_event(value)
    ):
        return True, (_FQ_STALE, _MATERIAL_STALE_EXPLICIT)
    if detectors.stale_day_only_context(value, now=now) or detectors.stale_quarter_context(
        value, now=now
    ):
        return True, (_FQ_STALE, _MATERIAL_STALE_DATED)
    return False, ()


def evaluate_story_admission(
    admission: StoryAdmissionInput | None = None,
    *,
    topic: str = "",
    headline: str = "",
    summary: str = "",
    source_text: str = "",
    subject: str = "",
    stage: StoryAdmissionStage | str = StoryAdmissionStage.VISIBLE,
    now: datetime | None = None,
) -> StoryAdmissionDecision:
    if admission is not None:
        if any((topic, headline, summary, source_text, subject)) or now is not None or stage != StoryAdmissionStage.VISIBLE:
            raise TypeError("pass StoryAdmissionInput or keyword fields, not both")
        topic = admission.topic
        headline = admission.headline
        summary = admission.summary
        source_text = admission.source_text
        subject = admission.subject
        stage = admission.stage
        now = admission.now

    resolved_stage = stage if isinstance(stage, StoryAdmissionStage) else StoryAdmissionStage(stage)
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reasons: list[StoryAdmissionReason] = []
    codes: list[str] = []

    def reject(reason: StoryAdmissionReason, *compatibility: str) -> None:
        reasons.append(reason)
        codes.extend(compatibility)

    if resolved_stage is StoryAdmissionStage.MATERIAL:
        text = source_text or summary
        if detectors.context_dependent_summary(text):
            reject(StoryAdmissionReason.STANDALONE_COMPLETENESS, _FQ_CONTEXT_SUMMARY, _MATERIAL_CONTEXT)
        if detectors.visible_metadata_text(text):
            reject(StoryAdmissionReason.METADATA, _FQ_METADATA, _MATERIAL_NON_EVENT)
        if detectors.malformed_visible_text(text):
            reject(StoryAdmissionReason.MALFORMED, _FQ_MALFORMED, _MATERIAL_CONTEXT)
        if detectors.conditional_analytical_text(text):
            reject(StoryAdmissionReason.NON_EVENT_DESCRIPTION, _FQ_CONDITIONAL, _MATERIAL_CONDITIONAL)
        if detectors.non_event_analytical_text(text):
            reject(StoryAdmissionReason.NON_EVENT_DESCRIPTION, _FQ_NON_EVENT, _MATERIAL_NON_EVENT)
        if _biographical_text(text):
            reject(StoryAdmissionReason.BIOGRAPHY, _FQ_NON_EVENT, _MATERIAL_NON_EVENT)
        stale, stale_codes = _freshness_codes(text, now=reference)
        if stale:
            reject(StoryAdmissionReason.FRESHNESS, *stale_codes)
        if detectors.mixed_event_summary(text):
            reject(StoryAdmissionReason.MIXED_BINDING, _FQ_MIXED, _MATERIAL_CONTEXT)
            reasons.append(StoryAdmissionReason.EVENT_CENTRALITY)
        return StoryAdmissionDecision(
            stage=resolved_stage,
            accepted=not reasons,
            reasons=_dedupe(reasons),
            compatibility_codes=_dedupe(codes),
        )

    visible_text = summary or source_text
    if detectors.context_dependent_headline(headline):
        reject(StoryAdmissionReason.STANDALONE_COMPLETENESS, _FQ_CONTEXT_HEADLINE)
    if detectors.context_dependent_summary(visible_text):
        reject(StoryAdmissionReason.STANDALONE_COMPLETENESS, _FQ_CONTEXT_SUMMARY)
    if detectors.headline_summary_collision(headline=headline, summary=visible_text):
        reject(StoryAdmissionReason.STANDALONE_COMPLETENESS, _FQ_COLLISION)
    if detectors.visible_metadata_text(headline) or detectors.visible_metadata_text(visible_text):
        reject(StoryAdmissionReason.METADATA, _FQ_METADATA)
    if detectors.malformed_visible_text(headline) or detectors.malformed_visible_text(visible_text):
        reject(StoryAdmissionReason.MALFORMED, _FQ_MALFORMED)
    if detectors.conditional_analytical_text(visible_text):
        reject(StoryAdmissionReason.NON_EVENT_DESCRIPTION, _FQ_CONDITIONAL)
    if detectors.non_event_analytical_text(visible_text):
        reject(StoryAdmissionReason.NON_EVENT_DESCRIPTION, _FQ_NON_EVENT)
    if _biographical_text(visible_text):
        reject(StoryAdmissionReason.BIOGRAPHY, _FQ_NON_EVENT)
    if detectors.mixed_event_summary(visible_text):
        reject(StoryAdmissionReason.MIXED_BINDING, _FQ_MIXED)
        reasons.append(StoryAdmissionReason.EVENT_CENTRALITY)

    stale, stale_codes = _freshness_codes(visible_text, now=reference)
    if stale:
        reject(StoryAdmissionReason.FRESHNESS, *stale_codes)
        # A stale/background proposition promoted as today's visible event is also a
        # centrality failure. Keeping this additive reason makes the policy explicit
        # without changing any legacy FEED_QUALITY error surface.
        reasons.append(StoryAdmissionReason.EVENT_CENTRALITY)

    if _bare_unattributed_forecast(visible_text):
        reject(
            StoryAdmissionReason.FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED,
            _FQ_CONTEXT_SUMMARY,
        )

    if topic in _KBO_TOPIC_NAMES and _kbo_topic_ownership_violation(headline, visible_text):
        reject(StoryAdmissionReason.TOPIC_OWNERSHIP, _FQ_TOPIC)
    elif topic in _KPOP_TOPIC_NAMES and _kpop_topic_ownership_violation(headline):
        reject(StoryAdmissionReason.TOPIC_OWNERSHIP, _FQ_TOPIC)

    return StoryAdmissionDecision(
        stage=resolved_stage,
        accepted=not reasons,
        reasons=_dedupe(reasons),
        compatibility_codes=_dedupe(codes),
    )


# The detector module is a byte-preserved extraction of the former feed_quality
# implementation. Replace its old composite entry point at runtime so there is no
# second active admission path; all callers converge here.
def _detector_visible_story_issues(*, topic: str, headline: str, summary: str):
    decision = evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
    )
    known = {item.value: item for item in detectors.VisibleStoryIssue}
    return tuple(known[code] for code in decision.compatibility_codes if code in known)


detectors.visible_story_issues = _detector_visible_story_issues
