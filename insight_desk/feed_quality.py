from __future__ import annotations

# Low-level deterministic detectors remain public for compatibility. Policy
# composition moved to story_admission; this module is now only a detector façade
# plus the legacy visible-story adapter.
from insight_desk.feed_quality_detectors import *  # noqa: F401,F403
from insight_desk.feed_quality_detectors import VisibleStoryIssue
from insight_desk.story_admission import StoryAdmissionStage, evaluate_story_admission


def visible_story_issues(
    *,
    topic: str,
    headline: str,
    summary: str,
) -> tuple[VisibleStoryIssue, ...]:
    decision = evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
    )
    known = {item.value: item for item in VisibleStoryIssue}
    return tuple(
        known[code]
        for code in decision.compatibility_codes
        if code in known
    )
