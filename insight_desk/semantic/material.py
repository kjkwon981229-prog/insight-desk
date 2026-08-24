from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from functools import lru_cache
import re
from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact

from .tooling import KiwiMorphologyHelper


_EXPLICIT_NOMINAL_MATERIAL_ACTIONS = frozenset({"선발투수 예고"})
_PUBLISHER_NOTICE_PERMISSION_CUES = ("무단", "사전허가없이", "사전 허가 없이")
_PUBLISHER_NOTICE_RESTRICTION_TERMS = ("복사", "배포", "전재", "재배포", "판매")
_PUBLISHER_NOTICE_LEGAL_CUES = ("책임", "금지", "저작권")
_SPORTS_CONTEXT_CUES = ("경기에서", "전에서", "경기 중", "경기에")
_SPORTS_DEPICTIVE_ACTION_CUES = (
    "투구",
    "타격",
    "수비",
    "훈련",
    "캐치볼",
    "몸을 풀",
    "세리머니",
    "포즈",
)
_SPORTS_DEPICTIVE_ENDINGS = ("고 있다", "고 있다.", "고 있습니다", "고 있습니다.")
_CONTEXT_DEPENDENT_LEADS = (
    "여기에 ",
    "여기에,",
    "이후 ",
    "이 딜러는 ",
    "이번 ",
    "팬들의 ",
)
_CONTEXT_DEPENDENT_PHRASES = ("이번 상황",)
_GENERIC_REFERENTIAL_SUBJECTS = frozenset({"그", "그가", "그는", "그녀", "그녀가", "그녀는", "이들", "이들이", "이들은"})
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
_NON_EVENT_ANALYTICAL_ENDINGS = (
    "설명하기 어렵다",
    "설명하기 힘들다",
    "것으로 보인다",
    "것으로 보입니다",
    "것으로 풀이된다",
    "것으로 풀이됩니다",
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
_STALE_DATE_CONTEXT_CUES = ("공개된", "열린", "개최된", "진행된", "발표된", "출시된", "방송된")
_STALE_SPORTS_RETROSPECTIVE_ENDINGS = ("나왔다", "벌어졌다", "기록됐다", "기록되었다")
_PAST_YEAR_BACKGROUND_CUES = ("부터", "이후", "이래")
_CURRENT_EVENT_CUES = ("올해", "오늘", "현재", "최근")
_SENTENCE_TERMINALS = ".!?。！？"
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})년")
_MONTH_DAY_RE = re.compile(r"(?<!\d)(?:(20\d{2})년\s*)?(1[0-2]|0?[1-9])월\s*([0-2]?\d|3[01])일")
_MONTH_DAY_ONLY_RE = re.compile(r"(?:1[0-2]|0?[1-9])월(?:\s*(?:[0-2]?\d|3[01])일)?")
_CONDITIONAL_SCENARIO_RE = re.compile(r"\s(?:경우|시)\s")


class MaterialEventVerdict(StrEnum):
    MATERIAL = "material"
    DEFER = "defer"


class MaterialEventReason(StrEnum):
    EVIDENCE_BOUND_EXPLICIT_PREDICATE = "evidence_bound_explicit_predicate"
    EVIDENCE_BOUND_EXPLICIT_NOMINAL_EVENT = "evidence_bound_explicit_nominal_event"
    FACT_MISSING = "fact_missing"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_OUTSIDE_EVENT = "evidence_outside_event"
    FACT_FIELD_NOT_LITERAL = "fact_field_not_literal"
    PUBLISHER_NOTICE_BOILERPLATE = "publisher_notice_boilerplate"
    DEPICTIVE_SPORTS_CAPTION = "depictive_sports_caption"
    CONTEXT_DEPENDENT_FRAGMENT = "context_dependent_fragment"
    NON_EVENT_ANALYTICAL_JUDGMENT = "non_event_analytical_judgment"
    CONDITIONAL_ANALYTICAL_SCENARIO = "conditional_analytical_scenario"
    STALE_DATED_CONTEXT = "stale_dated_context"
    STALE_EXPLICIT_PAST_EVENT = "stale_explicit_past_event"
    STALE_SPORTS_RETROSPECTIVE = "stale_sports_retrospective"
    PREDICATE_SIGNAL_MISSING = "predicate_signal_missing"
    LOCAL_HELPER_UNAVAILABLE = "local_helper_unavailable"


@dataclass(frozen=True, slots=True)
class MaterialEventAssessment:
    event_id: str
    verdict: MaterialEventVerdict
    reasons: tuple[MaterialEventReason, ...]

    @property
    def selection_signal(self) -> bool | None:
        return True if self.verdict is MaterialEventVerdict.MATERIAL else None


@lru_cache(maxsize=1)
def _shared_morphology() -> KiwiMorphologyHelper:
    return KiwiMorphologyHelper()


def _cited_text(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> tuple[str | None, MaterialEventReason | None]:
    parts: list[str] = []
    allowed_articles = set(event.article_ids)
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None:
            return None, MaterialEventReason.EVIDENCE_MISSING
        if span.article_id not in allowed_articles:
            return None, MaterialEventReason.EVIDENCE_OUTSIDE_EVENT
        parts.append(span.text)
    return "\n\n".join(parts), None


def _publisher_notice_boilerplate(text: str) -> bool:
    return (
        any(cue in text for cue in _PUBLISHER_NOTICE_PERMISSION_CUES)
        and sum(term in text for term in _PUBLISHER_NOTICE_RESTRICTION_TERMS) >= 2
        and any(cue in text for cue in _PUBLISHER_NOTICE_LEGAL_CUES)
    )


def _standalone_sports_photo_caption(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) > 180:
        return False
    if sum(normalized.count(mark) for mark in ".!?。！？") > 1:
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if not any(cue in normalized for cue in _SPORTS_DEPICTIVE_ACTION_CUES):
        return False
    return normalized.endswith(_SPORTS_DEPICTIVE_ENDINGS)


def _bare_ranking_fragment(normalized: str) -> bool:
    has_bare_ranking = (
        any(cue in normalized for cue in _BARE_RANKING_CUES)
        or re.search(r"\d+\s*주\s*연속\s*1위", normalized) is not None
    )
    if not has_bare_ranking:
        return False
    folded = normalized.casefold()
    return not any(term.casefold() in folded for term in _BARE_RANKING_CONTEXT_TERMS)


def _context_dependent_fragment(text: str, *, subject: str) -> bool:
    normalized = " ".join(text.split())
    if subject.strip() in _GENERIC_REFERENTIAL_SUBJECTS:
        return True
    if any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_LEADS):
        return True
    if any(phrase in normalized for phrase in _CONTEXT_DEPENDENT_PHRASES):
        return True
    if _BARE_ANNIVERSARY_LEAD_RE.search(normalized) is not None:
        return True
    return _bare_ranking_fragment(normalized)


def _non_event_analytical_judgment(text: str) -> bool:
    normalized = " ".join(text.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    return normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS)


def _conditional_analytical_scenario(text: str) -> bool:
    normalized = " ".join(text.split())
    has_reporting_event = any(cue in normalized for cue in _CONDITIONAL_EVENT_CUES)
    if "더라도" in normalized and "이어야" in normalized:
        return not has_reporting_event
    if _CONDITIONAL_SCENARIO_RE.search(normalized) is None:
        return False
    return not has_reporting_event


def _stale_sports_retrospective(text: str) -> bool:
    normalized = " ".join(text.split())
    years = [int(value) for value in _YEAR_RE.findall(normalized)]
    if not years or not any(year < datetime.now(timezone.utc).year for year in years):
        return False
    if not any(cue in normalized for cue in _SPORTS_CONTEXT_CUES):
        return False
    if "장면" not in normalized and "기록" not in normalized:
        return False
    terminal_stripped = normalized.rstrip(_SENTENCE_TERMINALS).rstrip()
    return terminal_stripped.endswith(_STALE_SPORTS_RETROSPECTIVE_ENDINGS)


def _explicit_past_year_event(text: str, *, fact: EventFact) -> bool:
    normalized = " ".join(text.split())
    now_year = datetime.now(timezone.utc).year
    past_matches = [match for match in _YEAR_RE.finditer(normalized) if int(match.group(1)) < now_year]
    if not past_matches:
        return False
    if f"{now_year}년" in normalized or any(cue in normalized for cue in _CURRENT_EVENT_CUES):
        return False

    subject = " ".join(fact.subject.split())
    action = " ".join(fact.action.split())
    subject_pos = normalized.find(subject) if subject else -1
    action_pos = normalized.find(action) if action else -1

    for match in past_matches:
        if subject_pos >= 0 and match.end() <= subject_pos:
            between = normalized[match.end() : subject_pos]
            date_remainder = _MONTH_DAY_ONLY_RE.sub("", between)
            if not date_remainder.strip(" \t,·"):
                return True

        if action_pos >= 0 and action_pos <= match.start() <= action_pos + 24:
            following = normalized[match.end() : match.end() + 8].lstrip()
            if any(following.startswith(cue) for cue in _PAST_YEAR_BACKGROUND_CUES):
                continue
            return True
    return False


def _dated_context_is_stale(text: str) -> bool:
    if _stale_sports_retrospective(text):
        return False
    normalized = " ".join(text.split())
    now = datetime.now(timezone.utc)
    for match in _MONTH_DAY_RE.finditer(normalized):
        if match.start() > 32:
            continue
        year_text, month_text, day_text = match.groups()
        year = int(year_text) if year_text is not None else now.year
        try:
            candidate = datetime(year, int(month_text), int(day_text), tzinfo=timezone.utc)
        except ValueError:
            continue
        if year_text is None and candidate > now + timedelta(hours=6):
            try:
                candidate = candidate.replace(year=year - 1)
            except ValueError:
                continue
        if now - candidate <= timedelta(hours=72):
            continue
        tail = normalized[match.end() : match.end() + 24]
        if any(cue in tail for cue in _STALE_DATE_CONTEXT_CUES):
            return True
    return False


def assess_material_event(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: KiwiMorphologyHelper | None = None,
) -> MaterialEventAssessment:
    if morphology is None:
        try:
            morphology = _shared_morphology()
        except RuntimeError:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.LOCAL_HELPER_UNAVAILABLE,),
            )

    used_nominal = False
    for fact_id in event.fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            return MaterialEventAssessment(
                event.event_id, MaterialEventVerdict.DEFER, (MaterialEventReason.FACT_MISSING,)
            )
        text, evidence_error = _cited_text(event, fact, evidence)
        if evidence_error is not None or text is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (evidence_error or MaterialEventReason.EVIDENCE_MISSING,),
            )
        if _publisher_notice_boilerplate(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.PUBLISHER_NOTICE_BOILERPLATE,),
            )
        if _standalone_sports_photo_caption(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.DEPICTIVE_SPORTS_CAPTION,),
            )
        if _context_dependent_fragment(text, subject=fact.subject):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
            )
        if _non_event_analytical_judgment(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
            )
        if _conditional_analytical_scenario(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.CONDITIONAL_ANALYTICAL_SCENARIO,),
            )
        if _stale_sports_retrospective(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.STALE_SPORTS_RETROSPECTIVE,),
            )
        if _explicit_past_year_event(text, fact=fact):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT,),
            )
        if _dated_context_is_stale(text):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.STALE_DATED_CONTEXT,),
            )
        literal_fields = (fact.subject, fact.action) + ((fact.object,) if fact.object is not None else ())
        if any(value not in text for value in literal_fields):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_FIELD_NOT_LITERAL,),
            )
        if any(token.tag in {"VV", "XSV"} for token in morphology.analyze(fact.action)):
            continue
        if fact.action in _EXPLICIT_NOMINAL_MATERIAL_ACTIONS:
            used_nominal = True
            continue
        return MaterialEventAssessment(
            event.event_id,
            MaterialEventVerdict.DEFER,
            (MaterialEventReason.PREDICATE_SIGNAL_MISSING,),
        )

    reason = (
        MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_NOMINAL_EVENT
        if used_nominal
        else MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE
    )
    return MaterialEventAssessment(event.event_id, MaterialEventVerdict.MATERIAL, (reason,))
