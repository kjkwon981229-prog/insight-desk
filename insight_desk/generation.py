from __future__ import annotations

from enum import StrEnum
import re

# Preserve the generation/preservation contract byte-for-byte in generation_core;
# this façade owns the one shared story-admission boundary for every generator.
from insight_desk.generation_core import *  # noqa: F401,F403
from insight_desk.generation_core import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    Groq20BBriefingGenerator as _CoreGroq20BBriefingGenerator,
    PreservationIssue,
    PreservationIssueCode,
    PreservationReport,
    validate_preservation as _core_validate_preservation,
)
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


_TOPIC_NAMES = {
    "kbo_hanwha": "KBO·한화 이글스",
    "kpop": "엔터·음악·K-POP",
    "ai_tech": "AI·테크",
    "economy": "경제·투자",
}
_GENERIC_PRIMARY_SUBJECTS = frozenset(
    {
        "회사",
        "기업",
        "업체",
        "관계자",
        "당국",
        "그",
        "그가",
        "그는",
        "그녀",
        "그녀가",
        "그녀는",
        "이들",
        "이들이",
        "이들은",
    }
)
_ISO_EVENT_DATE_RE = re.compile(
    r"^(?P<year>20\d{2})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])$"
)
_DURATION_AFTER_DAY_RE = r"(?:동안|간|후|뒤|째|만에|내에|이내)"


class _FacadePreservationIssueCode(StrEnum):
    MISSING_EVENT_DATE = "missing_event_date"


def _event_date_parts(event_date: str) -> tuple[int, int, int] | None:
    match = _ISO_EVENT_DATE_RE.fullmatch(event_date.strip())
    if match is None:
        return None
    return int(match.group("year")), int(match.group("month")), int(match.group("day"))


def _event_date_is_visible(text: str, event_date: str) -> bool:
    normalized = " ".join(text.split())
    if event_date in normalized:
        return True
    parts = _event_date_parts(event_date)
    if parts is None:
        return False
    year, month, day = parts
    patterns = (
        rf"(?<!\d){year}년\s*0?{month}월\s*0?{day}일(?!\s*{_DURATION_AFTER_DAY_RE})",
        rf"(?<!\d)0?{month}월\s*0?{day}일(?!\s*{_DURATION_AFTER_DAY_RE})",
        rf"(?<!\d)0?{day}일(?!\s*{_DURATION_AFTER_DAY_RE})",
    )
    return any(re.search(pattern, normalized) is not None for pattern in patterns)


def _inherited_event_dates(request: GenerationRequest) -> tuple[str, ...]:
    dates: list[str] = []
    seen: set[str] = set()
    for fact_id in request.event.fact_ids:
        fact = request.facts[fact_id]
        event_date = (fact.event_date or "").strip()
        if not event_date or event_date in seen:
            continue
        cited = "\n".join(
            request.evidence[evidence_id].text
            for evidence_id in fact.evidence_ids
            if evidence_id in request.evidence
        )
        if _event_date_is_visible(cited, event_date):
            continue
        seen.add(event_date)
        dates.append(event_date)
    return tuple(dates)


def _event_date_number_aliases(event_date: str) -> frozenset[str]:
    parts = _event_date_parts(event_date)
    if parts is None:
        return frozenset({event_date})
    year, month, day = parts
    return frozenset(
        {
            event_date,
            f"{year}년",
            f"{month}월",
            f"{day}일",
            f"0{month}월" if month < 10 else f"{month}월",
            f"0{day}일" if day < 10 else f"{day}일",
        }
    )


def validate_preservation(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> PreservationReport:
    """Extend the frozen core preservation report with inherited event-date retention.

    Semantic extraction can bind a date from the immediately preceding source sentence onto an
    EventFact while its sentence-sized evidence remains date-less. That bound date is trusted fact
    context, so every generation route—including exact-source fallback—must keep it visible instead
    of promoting the old event as undated current news.
    """

    core_report = _core_validate_preservation(request, draft)
    inherited_dates = _inherited_event_dates(request)
    if not inherited_dates:
        return core_report

    issues = list(core_report.issues)
    generated = draft.combined_text
    for event_date in inherited_dates:
        if _event_date_is_visible(generated, event_date):
            allowed_values = _event_date_number_aliases(event_date)
            issues = [
                issue
                for issue in issues
                if not (
                    issue.code
                    in {
                        PreservationIssueCode.NOVEL_DATE,
                        PreservationIssueCode.NOVEL_NUMBER,
                    }
                    and issue.value in allowed_values
                )
            ]
            continue
        issues.append(
            PreservationIssue(
                _FacadePreservationIssueCode.MISSING_EVENT_DATE,
                event_date,
            )
        )
    return PreservationReport(accepted=not issues, issues=tuple(issues))


def _evidence_bound_actor_subjects(request: GenerationRequest) -> tuple[str, ...]:
    """Return concrete EventFact subjects literally present in their cited evidence bytes."""

    subjects: list[str] = []
    seen: set[str] = set()
    for fact_id in request.event.fact_ids:
        fact = request.facts[fact_id]
        subject = fact.subject.strip()
        if not subject or subject in _GENERIC_PRIMARY_SUBJECTS:
            continue
        cited = "\n".join(request.evidence[eid].text for eid in fact.evidence_ids)
        if subject not in cited or subject in seen:
            continue
        seen.add(subject)
        subjects.append(subject)
    return tuple(subjects)


def validate_generated_actor_preservation(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> None:
    """Reject provider rewrites that erase every concrete evidence-bound event actor.

    This is generation preservation, not general visible admission. Exact-source fallback is exempt:
    it is already constrained to immutable source bytes and the shared standalone story contract.
    Provider prose, however, may remain entailed after dropping who the event is about; requiring at
    least one concrete EventFact actor in the visible card closes that discourse-loss path without
    assuming that the first fact is always the one selected for the rewrite.
    """

    subjects = _evidence_bound_actor_subjects(request)
    if not subjects:
        return
    combined = draft.combined_text.casefold()
    if not any(subject.casefold() in combined for subject in subjects):
        raise GenerationContractError("generated draft drops all evidence-bound event actors")


def validate_story_admission(request: GenerationRequest, draft: GeneratedDraft) -> None:
    topic = _TOPIC_NAMES.get(request.event.topic_id, request.event.topic_id)
    visible_decision = evaluate_story_admission(
        topic=topic,
        headline=draft.headline,
        summary=draft.summary,
        source_text=request.evidence_text,
        stage=StoryAdmissionStage.VISIBLE,
    )

    # The visible rewrite may omit a stale date phrase that is present in the
    # event evidence. Reuse the same shared decision on the source/material
    # representation and project only FRESHNESS. Other material-side reasons are
    # intentionally not promoted: descriptive or historical background remains
    # allowed when the primary event itself is current.
    evidence_decision = evaluate_story_admission(
        topic=topic,
        source_text=request.evidence_text,
        stage=StoryAdmissionStage.MATERIAL,
    )
    evidence_stale = StoryAdmissionReason.FRESHNESS in evidence_decision.reasons

    if not visible_decision.accepted or evidence_stale:
        reasons = list(visible_decision.reasons)
        if evidence_stale and StoryAdmissionReason.FRESHNESS not in reasons:
            reasons.append(StoryAdmissionReason.FRESHNESS)
        reason_text = ",".join(reason.value for reason in reasons)
        raise GenerationContractError(
            f"story admission rejected generated draft: {reason_text}"
        )


class Groq20BBriefingGenerator(_CoreGroq20BBriefingGenerator):
    def generate(self, request: GenerationRequest):
        draft = super().generate(request)
        validate_story_admission(request, draft)
        return draft
