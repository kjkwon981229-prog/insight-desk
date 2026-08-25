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
