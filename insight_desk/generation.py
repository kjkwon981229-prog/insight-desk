from __future__ import annotations

# Preserve the generation/preservation contract byte-for-byte in generation_core;
# this façade owns the one shared story-admission boundary for every generator.
from insight_desk.generation_core import *  # noqa: F401,F403
from insight_desk.generation_core import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    Groq20BBriefingGenerator as _CoreGroq20BBriefingGenerator,
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
        validate_generated_actor_preservation(request, draft)
        return draft
