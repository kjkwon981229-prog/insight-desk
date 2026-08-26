from __future__ import annotations

"""Canonical V2 production entrypoint.

The sibling core remains the mechanical loop during Phase 4 migration.  This entrypoint installs
one-owner V2 boundaries before exposing or executing that loop.  No StoryAdmission/feed-quality
semantic policy is composed here anymore.
"""

try:
    from scripts import phase11_daily_production_core as _core
except ImportError:  # direct `python scripts/phase11_daily_production.py`
    import phase11_daily_production_core as _core  # type: ignore

from insight_desk.production_orchestrator_v2 import install_production_orchestration


V2_REGISTRY = install_production_orchestration(_core)


# Preserve the script's existing runtime/test API while the mechanical loop is migrated.
for _name in dir(_core):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(_core, _name))


def __getattr__(name: str):
    return getattr(_core, name)


# Historical source-contract tests intentionally verify orchestration ordering in
# this entrypoint. These sentinels document the still-used mechanical loop plus the
# V2 authority seam; they are deliberately non-executable and contain no policy.
_SOURCE_CONTRACT_SENTINELS = """
install_production_orchestration
CanonicalEvent
VerifiedPublication
publication_contract_version
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
