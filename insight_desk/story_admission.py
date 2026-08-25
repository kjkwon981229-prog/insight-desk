from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Mapping

from insight_desk import feed_quality_detectors as detectors
from insight_desk.core import CandidateEvent, EventFact, EvidenceSpan


class StoryAdmissionStage(StrEnum):
    MATERIAL = "material"
    ROUTING = "routing"
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
    event: CandidateEvent | None = None
    facts: Mapping[str, EventFact] | None = None
    evidence: Mapping[str, EvidenceSpan] | None = None
    intent_anchors: tuple[str, ...] = ()
    required_intent_terms: tuple[str, ...] = ()
    event_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoryAdmissionDecision:
    stage: StoryAdmissionStage
    accepted: bool
    reasons: tuple[StoryAdmissionReason, ...]
    compatibility_codes: tuple[str, ...] = ()


_AI_TECH_TOPIC_ID = "ai_tech"
_KBO_TOPIC_NAMES = frozenset({"KBO·한화 이글스", "kbo_hanwha"})
_KBO_TOPIC_ID = "kbo_hanwha"
_KPOP_TOPIC_NAMES = frozenset({"엔터·음악·K-POP", "kpop"})
_GENERIC_REFERENTIAL_SUBJECTS = frozenset(
    {"그", "그가", "그는", "그녀", "그녀가", "그녀는", "이들", "이들이", "이들은"}
)
_KBO_ENTERTAINMENT_ENTITY_CUES = ("그룹", "아이돌", "멤버", "가수", "배우")
_KBO_ENTERTAINMENT_ACTION_CUES = ("승리 요정", "시구", "시타")
_KBO_COMPETITIVE_EVENT_CUES = (
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
    "퓨처스리그",
    "기록",
)
_KBO_NON_BASEBALL_PARTNERSHIP_CUES = ("의료지원", "협력병원", "한의치료", "병원")
_KBO_RANK_CUES = ("순위", "리그 1위", "리그 2위", "리그 3위", "리그 4위", "리그 5위")
_KBO_HEADLINE_SCOPE_CUES = ("한화", "KBO", "프로야구")
_HANWHA_OPPONENT_RE = re.compile(
    r"한화(?:\s+이글스)?(?:전|와의\s+경기|와\s+경기|와의\s+맞대결|를|을)"
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
_STALE_PRIOR_POLICY_EVENT_RE = re.compile(
    r"(?:지난달|지난\s+달|지난\s+분기|지난\s+연도)"
    r"[^.!?。！？]{0,140}?(?:기준금리|정책금리|금리)"
    r"[^.!?。！？]{0,100}?(?:올렸|내렸|인상했|인하했|동결했)"
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
_HANWHA_PRIOR_GAME_REFERENCE_RE = re.compile(r"한화(?:\s+이글스)?전\s*(?:이후|이래|뒤)")
_HANWHA_GAMES_PLAYED_COMPARISON_RE = re.compile(
    r"한화(?:\s+이글스)?(?:보다(?:는)?|와\s+마찬가지|\s*대비)"
    r"[^.!?。！？]{0,40}?\d+\s*경기[^.!?。！？]{0,40}?"
    r"(?:덜|적게|많이|더)\s*(?:경기(?:를)?\s*)?치렀"
)
_HANWHA_SUBORDINATE_CONTEXT_CUES = ("가운데", "한편", "사진", "배경")
_HANWHA_DIRECT_ACTION_CUES = (
    "상대로",
    "누르고",
    "꺾고",
    "제압",
    "이겼",
    "승리했다",
    "패했다",
    "홈런",
    "삼진",
    "등판",
    "선발",
    "부상",
    "트레이드",
)
_KBO_EVENT_TERM_ALIASES = {
    "결과": ("누르고", "꺾고", "이겼", "제압", "완파"),
    "승리": ("누르고", "꺾고", "이겼", "제압", "완파"),
    "패배": ("패했다", "패전", "졌다"),
}
_KBO_RANK_SURFACE_RE = re.compile(r"(?<!\d)\d+\s*위(?!\d)")


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
_MATERIAL_PUBLISHER_NOTICE = "MATERIAL_PUBLISHER_NOTICE_BOILERPLATE"
_MATERIAL_DEPICTIVE_SPORTS = "MATERIAL_DEPICTIVE_SPORTS_CAPTION"


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


def _stale_prior_policy_event(value: str) -> bool:
    return _STALE_PRIOR_POLICY_EVENT_RE.search(" ".join(value.split())) is not None


def _bare_unattributed_forecast(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(".!?。！？").rstrip()
    if len(normalized) > 35 or _BARE_FORECAST_END_RE.search(normalized) is None:
        return False
    return not any(cue in normalized for cue in _FORECAST_ATTRIBUTION_CUES)


def _kbo_topic_ownership_violation(headline: str, summary: str) -> bool:
    combined = " ".join(f"{headline} {summary}".split())
    if "한화" not in combined:
        return True
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
        and not any(cue in combined for cue in _KBO_COMPETITIVE_EVENT_CUES)
    ):
        return True
    if _HANWHA_OPPONENT_RE.search(combined) is not None and any(
        cue in combined for cue in _KBO_RANK_CUES
    ):
        lead = headline.split(",", 1)[0].strip()
        if "한화" not in lead:
            return True
    if (
        detectors.context_dependent_headline(headline)
        and not any(cue.casefold() in headline.casefold() for cue in _KBO_HEADLINE_SCOPE_CUES)
    ):
        return True
    return False


def _kpop_topic_ownership_violation(headline: str) -> bool:
    folded = headline.casefold()
    if any(cue.casefold() in folded for cue in _KPOP_HEADLINE_SCOPE_CUES):
        return False
    # A named K-culture venue/event with an explicit exhibition is a valid
    # entertainment event even when the compact headline omits the word K-POP.
    return not ("k-문화" in folded and "전시" in headline)


def _freshness_codes(value: str, *, now: datetime) -> tuple[bool, tuple[str, ...]]:
    if _stale_sports_retrospective(value, now=now):
        return True, (_FQ_STALE_SPORTS, _MATERIAL_STALE_SPORTS)
    if (
        detectors.stale_explicit_past_event_text(value, now=now)
        or detectors.stale_relative_past_event_text(value)
        or detectors.stale_relative_period_event_text(value)
        or _stale_prior_policy_event(value)
    ):
        return True, (_FQ_STALE, _MATERIAL_STALE_EXPLICIT)
    if detectors.stale_day_only_context(value, now=now) or detectors.stale_quarter_context(
        value, now=now
    ):
        return True, (_FQ_STALE, _MATERIAL_STALE_DATED)
    return False, ()


def _term_present(text: str, term: str) -> bool:
    term = term.strip()
    if not term:
        return False
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+&/-]*", term):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return term.casefold() in text.casefold()


def _fact_surface(fact: EventFact) -> str:
    return " ".join(value for value in (fact.subject, fact.action, fact.object or "") if value)


def _fact_has_topic_anchor(fact: EventFact, intent_anchors: tuple[str, ...]) -> bool:
    surface = _fact_surface(fact)
    return any(_term_present(surface, term) for term in intent_anchors)


def _fact_has_configured_kbo_event_term(fact: EventFact, event_terms: tuple[str, ...]) -> bool:
    surface = _fact_surface(fact)
    for term in event_terms:
        if _term_present(surface, term):
            return True
        if any(alias in surface for alias in _KBO_EVENT_TERM_ALIASES.get(term, ())):
            return True
        if term == "순위" and _KBO_RANK_SURFACE_RE.search(surface) is not None:
            return True
    return False


def _fact_has_kbo_rank_change(fact: EventFact, event_terms: tuple[str, ...]) -> bool:
    if "순위" not in event_terms:
        return False
    surface = _fact_surface(fact)
    return _term_present(surface, "순위") or _KBO_RANK_SURFACE_RE.search(surface) is not None


def _kbo_entertainment_crossover(facts: tuple[EventFact, ...], cited_text: tuple[str, ...]) -> bool:
    fact_text = "\n".join(_fact_surface(fact) for fact in facts)
    combined = f"{fact_text}\n{' '.join(cited_text)}"
    return (
        any(cue in combined for cue in _KBO_ENTERTAINMENT_ENTITY_CUES)
        and any(cue in combined for cue in _KBO_ENTERTAINMENT_ACTION_CUES)
    )


def _hanwha_fact_subject_central(fact: EventFact, cited_text: tuple[str, ...]) -> bool:
    subject = fact.subject.strip()
    if "한화" in subject:
        return True
    if not subject:
        return False
    for text in cited_text:
        normalized = " ".join(text.split())
        pattern = rf"한화(?:\s+이글스)?(?:의|\s+)\s*{re.escape(subject)}"
        if re.search(pattern, normalized):
            return True
    return False


def _hanwha_fact_directly_bound(fact: EventFact, cited_text: tuple[str, ...]) -> bool:
    subject = fact.subject.strip()
    object_text = (fact.object or "").strip()
    action = fact.action.strip()
    if "한화" in subject:
        return True
    fact_surface = " ".join(value for value in (subject, action, object_text) if value)
    if _HANWHA_GAMES_PLAYED_COMPARISON_RE.search(fact_surface) is not None:
        return False
    direct_action = any(cue in action for cue in _HANWHA_DIRECT_ACTION_CUES)
    if not direct_action:
        for text in cited_text:
            normalized = " ".join(text.split())
            hanwha_position = normalized.find("한화")
            if hanwha_position < 0:
                continue
            prefix = normalized[max(0, hanwha_position - 100) : hanwha_position]
            if any(cue in prefix for cue in _HANWHA_SUBORDINATE_CONTEXT_CUES):
                return False
    if "한화" in object_text:
        return True
    action_without_prior_reference = _HANWHA_PRIOR_GAME_REFERENCE_RE.sub("", action)
    if "한화" in action_without_prior_reference:
        return True
    for text in cited_text:
        normalized = " ".join(text.split())
        for entity in (subject, object_text):
            if not entity:
                continue
            pattern = rf"한화(?:\s+이글스)?(?:의)?\s+{re.escape(entity)}"
            if re.search(pattern, normalized):
                return True
    return False


def _routing_decision(admission: StoryAdmissionInput) -> StoryAdmissionDecision:
    reasons: list[StoryAdmissionReason] = []

    def reject(reason: StoryAdmissionReason) -> None:
        reasons.append(reason)

    event = admission.event
    facts = admission.facts
    evidence = admission.evidence
    if event is None or facts is None or evidence is None or event.topic_id != admission.topic:
        reject(StoryAdmissionReason.TOPIC_OWNERSHIP)
        return StoryAdmissionDecision(
            stage=StoryAdmissionStage.ROUTING,
            accepted=False,
            reasons=_dedupe(reasons),
        )

    cited_text: list[str] = []
    event_facts: list[EventFact] = []
    cited_by_fact: dict[str, tuple[str, ...]] = {}
    seen_evidence: set[str] = set()
    for fact_id in event.fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            reject(StoryAdmissionReason.EVENT_CENTRALITY)
            break
        event_facts.append(fact)
        fact_cited_text: list[str] = []
        for evidence_id in fact.evidence_ids:
            span = evidence.get(evidence_id)
            if span is None or span.article_id not in event.article_ids:
                reject(StoryAdmissionReason.EVENT_CENTRALITY)
                break
            fact_cited_text.append(span.text)
            if evidence_id not in seen_evidence:
                seen_evidence.add(evidence_id)
                cited_text.append(span.text)
        cited_by_fact[fact.fact_id] = tuple(fact_cited_text)
        if reasons:
            break
    if reasons or not cited_text:
        if not reasons:
            reject(StoryAdmissionReason.EVENT_CENTRALITY)
        return StoryAdmissionDecision(
            stage=StoryAdmissionStage.ROUTING,
            accepted=False,
            reasons=_dedupe(reasons),
        )

    cited = tuple(cited_text)
    combined = "\n".join(cited)
    if not any(_term_present(combined, term) for term in admission.intent_anchors):
        reject(StoryAdmissionReason.TOPIC_OWNERSHIP)
    if admission.required_intent_terms and not any(
        _term_present(combined, term) for term in admission.required_intent_terms
    ):
        reject(StoryAdmissionReason.TOPIC_OWNERSHIP)
    if reasons:
        return StoryAdmissionDecision(
            stage=StoryAdmissionStage.ROUTING,
            accepted=False,
            reasons=_dedupe(reasons),
        )

    frozen_facts = tuple(event_facts)
    if admission.topic == _AI_TECH_TOPIC_ID:
        if not any(_fact_has_topic_anchor(fact, admission.intent_anchors) for fact in frozen_facts):
            reject(StoryAdmissionReason.EVENT_CENTRALITY)
    elif admission.topic == _KBO_TOPIC_ID:
        if _kbo_entertainment_crossover(frozen_facts, cited):
            reject(StoryAdmissionReason.TOPIC_OWNERSHIP)
        elif not any(
            _hanwha_fact_directly_bound(fact, cited_by_fact[fact.fact_id])
            and _fact_has_configured_kbo_event_term(fact, admission.event_terms)
            and (
                not _fact_has_kbo_rank_change(fact, admission.event_terms)
                or _hanwha_fact_subject_central(fact, cited_by_fact[fact.fact_id])
            )
            for fact in frozen_facts
        ):
            reject(StoryAdmissionReason.EVENT_CENTRALITY)

    return StoryAdmissionDecision(
        stage=StoryAdmissionStage.ROUTING,
        accepted=not reasons,
        reasons=_dedupe(reasons),
    )


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
    routing_admission: StoryAdmissionInput | None = None
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
        routing_admission = admission

    resolved_stage = stage if isinstance(stage, StoryAdmissionStage) else StoryAdmissionStage(stage)
    if resolved_stage is StoryAdmissionStage.ROUTING:
        if routing_admission is None:
            raise TypeError("routing admission requires StoryAdmissionInput")
        return _routing_decision(routing_admission)

    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reasons: list[StoryAdmissionReason] = []
    codes: list[str] = []

    def reject(reason: StoryAdmissionReason, *compatibility: str) -> None:
        reasons.append(reason)
        codes.extend(compatibility)

    if resolved_stage is StoryAdmissionStage.MATERIAL:
        text = source_text or summary
        if detectors.publisher_notice_boilerplate(text):
            reject(StoryAdmissionReason.METADATA, _MATERIAL_PUBLISHER_NOTICE)
        if detectors.standalone_sports_photo_caption(text):
            reject(StoryAdmissionReason.NON_EVENT_DESCRIPTION, _MATERIAL_DEPICTIVE_SPORTS)
        if subject.strip() in _GENERIC_REFERENTIAL_SUBJECTS or detectors.context_dependent_summary(text):
            reject(StoryAdmissionReason.STANDALONE_COMPLETENESS, _FQ_CONTEXT_SUMMARY, _MATERIAL_CONTEXT)
        if detectors.visible_metadata_text(text):
            reject(StoryAdmissionReason.METADATA, _FQ_METADATA, _MATERIAL_NON_EVENT)
        if detectors.malformed_visible_text(text):
            reject(StoryAdmissionReason.MALFORMED, _FQ_MALFORMED, _MATERIAL_CONTEXT)
            reasons.append(StoryAdmissionReason.STANDALONE_COMPLETENESS)
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
        reasons.append(StoryAdmissionReason.STANDALONE_COMPLETENESS)
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
