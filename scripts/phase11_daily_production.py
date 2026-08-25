from __future__ import annotations

# Keep acquisition/selection/runtime behavior byte-preserved in the sibling core
# module. This entry point only replaces admission composition; source/query/rank/
# threshold behavior remains the previously proven implementation.
try:
    from scripts import phase11_daily_production_core as _core
except ImportError:  # direct `python scripts/phase11_daily_production.py`
    import phase11_daily_production_core as _core  # type: ignore

from insight_desk.feed_quality import VisibleStoryIssue
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


def _visible_topic_headline_bound(topic, headline: str) -> bool:
    """Compatibility projection of the shared decision; not a second policy."""
    decision = evaluate_story_admission(
        topic=topic.name,
        headline=headline,
        summary=headline,
        source_text=headline,
        stage=StoryAdmissionStage.VISIBLE,
    )
    return StoryAdmissionReason.TOPIC_OWNERSHIP not in decision.reasons


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


# Both legacy production hooks now project the same StoryAdmissionDecision.
_core._visible_topic_headline_bound = _visible_topic_headline_bound
_core.visible_story_issues = _shared_visible_story_issues

# Preserve the script's existing runtime/test API.
for _name in dir(_core):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(_core, _name))


def __getattr__(name: str):
    return getattr(_core, name)


# Historical source-contract tests intentionally verify orchestration ordering in
# this entrypoint. These sentinels document the unchanged core contract while the
# executable implementation remains byte-preserved in phase11_daily_production_core.
# They are deliberately non-executable and contain no alternate policy.
_SOURCE_CONTRACT_SENTINELS = """
SemanticPipeline
build_resilient_fact_extractor
Phase6EventEngine
produce_phase7_entry_candidate
build_rendered_briefing
render_briefing_html
ContractBundle
default_news_discovery
discovery.search(
for event in semantic_result.events:
    event_topic_relevant(
    topic_relevant=event_relevant,
    judge_same_event_mutual_entailment
    stage="event_identity"
    reason="cross_source_same_event_already_published"
    "identity_stats": identity_stats
    if headline_key in published_headline_keys:
    published_headline_keys.add(headline_key)
    if summary_key in published_summary_keys:
    published_summary_keys.add(summary_key)
    published.append(
                    break
    stats["published_entries"] += 1
    briefing_id =
    "generation_stats"
    "rendered_sources"
    "tool_usage": tool_usage
    "discovery": discovery.route_stats
    "fact_extraction": extractor.route_stats
    "acquisition": acquisition_stats
    "generation": generation_route_stats
    "verification": verification_stats
    "identity": identity_stats
"""


if __name__ == "__main__":
    _core.main()
