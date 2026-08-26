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
_REPORTING_SIDE_ACTOR_RE = re.compile(
    r"(?P<actor>[가-힣A-Za-z0-9·&()/_+-]{1,40}\s+측)"
    r"(?:은|는|이|가)\s+(?:밝혔다|전했다|설명했다|발표했다)"
)
_INCOMPLETE_IDENTITY_ROLE_RE = re.compile(
    r"^[가-힣]\s+(?:국회의원|의원|회장|부회장|대표이사|대표|사장|부사장|"
    r"위원장|장관|차관|총재|감독|코치|교수|박사)$"
)
_PROSPECTIVE_TEMPORAL_STATES = frozenset({"planned", "announced_prospective", "resuming"})


class _FacadePreservationIssueCode(StrEnum):
    INVALID_EVENT_SUBJECT = "invalid_event_subject"
    MISSING_HEADLINE_SUBJECT = "missing_headline_subject"
    MISSING_EVENT_DATE = "missing_event_date"
    MISSING_EVENT_PARTICIPANT = "missing_event_participant"


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


def _novel_reporting_side_actors(source: str, generated: str) -> tuple[str, ...]:
    source_normalized = " ".join(source.split())
    generated_normalized = " ".join(generated.split())
    actors = {
        " ".join(match.group("actor").split())
        for match in _REPORTING_SIDE_ACTOR_RE.finditer(generated_normalized)
    }
    return tuple(sorted(actor for actor in actors if actor not in source_normalized))


def _primary_event_fact(request: GenerationRequest):
    """Return the production primary fact only when event identity is structurally singular."""

    if len(request.event.fact_ids) != 1:
        return None
    return request.facts[request.event.fact_ids[0]]


def _fact_cited_text(request: GenerationRequest, fact) -> str:
    return "\n".join(
        request.evidence[evidence_id].text
        for evidence_id in fact.evidence_ids
        if evidence_id in request.evidence
    )


def _normalized_surface_present(text: str, surface: str) -> bool:
    normalized_text = " ".join(text.split()).casefold()
    normalized_surface = " ".join(surface.split()).casefold()
    return bool(normalized_surface) and normalized_surface in normalized_text


def _incomplete_event_subject(subject: str) -> bool:
    return _INCOMPLETE_IDENTITY_ROLE_RE.fullmatch(" ".join(subject.split()).strip()) is not None


def _publication_identity_issues(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> tuple[PreservationIssue, ...]:
    """Enforce identity-bearing source slots at the common publication boundary.

    Phase 6A emits one fact per production candidate. Publication may paraphrase that fact, but it
    may not publish an already-incomplete named actor, erase a concrete evidence-bound primary
    subject from the standalone headline, or strip the date/counterparty that identifies a planned
    event. This is deliberately narrower than exact action-string preservation.
    """

    fact = _primary_event_fact(request)
    if fact is None:
        return ()

    issues: list[PreservationIssue] = []
    subject = fact.subject.strip()
    cited = _fact_cited_text(request, fact)

    if subject and _incomplete_event_subject(subject):
        issues.append(
            PreservationIssue(
                _FacadePreservationIssueCode.INVALID_EVENT_SUBJECT,
                subject,
            )
        )
    elif (
        subject
        and subject not in _GENERIC_PRIMARY_SUBJECTS
        and _normalized_surface_present(cited, subject)
        and not _normalized_surface_present(draft.headline, subject)
    ):
        issues.append(
            PreservationIssue(
                _FacadePreservationIssueCode.MISSING_HEADLINE_SUBJECT,
                subject,
            )
        )

    temporal_state = getattr(fact.temporal_state, "value", fact.temporal_state)
    if temporal_state in _PROSPECTIVE_TEMPORAL_STATES:
        event_date = (fact.event_date or "").strip()
        if event_date and not _event_date_is_visible(draft.combined_text, event_date):
            issues.append(
                PreservationIssue(
                    _FacadePreservationIssueCode.MISSING_EVENT_DATE,
                    event_date,
                )
            )

        participants = tuple(
            participant.strip()
            for participant in fact.participants
            if participant.strip()
            and participant.strip() != subject
            and _normalized_surface_present(cited, participant)
        )
        if participants and not any(
            _normalized_surface_present(draft.combined_text, participant)
            for participant in participants
        ):
            issues.append(
                PreservationIssue(
                    _FacadePreservationIssueCode.MISSING_EVENT_PARTICIPANT,
                    participants[0],
                )
            )

    return tuple(issues)


def _issue_key(issue: PreservationIssue) -> tuple[str, str]:
    code = getattr(issue.code, "value", str(issue.code))
    return str(code), issue.value


def validate_preservation(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> PreservationReport:
    """Extend the frozen core report with source-to-publication identity preservation.

    In addition to the measured date/attribution protections, every generation route—including
    exact-source fallback—must preserve the identity-bearing slots of the primary EventFact. Exact
    source bytes are not automatically publication-safe when a fallback selects only a clause and
    drops who/what-date/counterparty context.
    """

    core_report = _core_validate_preservation(request, draft)
    issues = list(core_report.issues)
    generated = draft.combined_text

    for event_date in _inherited_event_dates(request):
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

    existing = {_issue_key(issue) for issue in issues}
    for actor in _novel_reporting_side_actors(request.evidence_text, generated):
        issue = PreservationIssue(PreservationIssueCode.NOVEL_ATTRIBUTION, actor)
        key = _issue_key(issue)
        if key not in existing:
            issues.append(issue)
            existing.add(key)

    for issue in _publication_identity_issues(request, draft):
        key = _issue_key(issue)
        if key not in existing:
            issues.append(issue)
            existing.add(key)

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

    This remains an early provider-specific boundary. Exact-source fallback does not call this helper,
    but it now consumes the same common ``validate_preservation`` identity invariant before it can be
    accepted. Provider prose keeps this additional early failure classification for route telemetry.
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
