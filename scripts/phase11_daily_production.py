from __future__ import annotations

# Keep the large acquisition/selection runtime byte-preserved in the sibling core
# module so source/query/ranking/threshold behavior cannot drift during this
# structural change. Only the visible admission hook is replaced here.
try:
    from scripts import phase11_daily_production_core as _core
except ImportError:  # direct `python scripts/phase11_daily_production.py`
    import phase11_daily_production_core as _core  # type: ignore

from insight_desk.feed_quality import VisibleStoryIssue
from insight_desk.story_admission import StoryAdmissionStage, evaluate_story_admission


def _shared_visible_story_issues(
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


# The old pre-headline topic check was a second admission policy. Disable that
# independent path; the full item-local decision below runs before the core ever
# increments a published slot.
_core._visible_topic_headline_bound = lambda topic, headline: True
_core.visible_story_issues = _shared_visible_story_issues

# Preserve the script's existing public API and test imports.
for _name in dir(_core):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(_core, _name))


def __getattr__(name: str):
    return getattr(_core, name)


if __name__ == "__main__":
    _core.main()
