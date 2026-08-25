from __future__ import annotations

# Preserve the generation/preservation contract byte-for-byte in generation_core;
# this façade adds the shared admission gate without changing provider, prompt,
# ranking, source, or threshold behavior.
from insight_desk.generation_core import *  # noqa: F401,F403
from insight_desk.generation_core import (
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


class Groq20BBriefingGenerator(_CoreGroq20BBriefingGenerator):
    def generate(self, request: GenerationRequest):
        draft = super().generate(request)
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
        return draft
