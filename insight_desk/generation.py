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
from insight_desk.story_admission import StoryAdmissionStage, evaluate_story_admission


_TOPIC_NAMES = {
    "kbo_hanwha": "KBO·한화 이글스",
    "kpop": "엔터·음악·K-POP",
    "ai_tech": "AI·테크",
    "economy": "경제·투자",
}


def validate_story_admission(request: GenerationRequest, draft: GeneratedDraft) -> None:
    decision = evaluate_story_admission(
        topic=_TOPIC_NAMES.get(request.event.topic_id, request.event.topic_id),
        headline=draft.headline,
        summary=draft.summary,
        source_text=request.evidence_text,
        stage=StoryAdmissionStage.VISIBLE,
    )
    if not decision.accepted:
        reasons = ",".join(reason.value for reason in decision.reasons)
        raise GenerationContractError(f"story admission rejected generated draft: {reasons}")


class Groq20BBriefingGenerator(_CoreGroq20BBriefingGenerator):
    def generate(self, request: GenerationRequest):
        draft = super().generate(request)
        validate_story_admission(request, draft)
        return draft
