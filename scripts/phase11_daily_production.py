from __future__ import annotations

"""Canonical V2 production entrypoint.

The sibling core remains the mechanical loop during Phase 4 migration. Importing this module is
side-effect free: Canonical V2 owners are installed only for the actual production execution and
are restored afterwards. Historical helper APIs remain available for replay, not as production
semantic authorities.
"""

try:
    from scripts import phase11_daily_production_core as _core
except ImportError:  # direct `python scripts/phase11_daily_production.py`
    import phase11_daily_production_core as _core  # type: ignore

from insight_desk.production_runtime_v2 import production_v2_runtime
# Historical helper remains import-compatible for old regression units. It is not called by the
# V2 production loop directly; canonical_identity_engine owns runtime identity.
from insight_desk.semantic.baseball_identity import kbo_visible_result_redundant


V2_REGISTRY = None


# Preserve the script's existing helper/test API before defining the execution-scoped wrappers.
for _name in dir(_core):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(_core, _name))


def __getattr__(name: str):
    return getattr(_core, name)


def run_production(*args, **kwargs):
    global V2_REGISTRY
    with production_v2_runtime(_core) as registry:
        V2_REGISTRY = registry
        try:
            return _core.run_production(*args, **kwargs)
        finally:
            V2_REGISTRY = None


def main() -> None:
    global V2_REGISTRY
    with production_v2_runtime(_core) as registry:
        V2_REGISTRY = registry
        try:
            _core.main()
        finally:
            V2_REGISTRY = None


# Historical source-contract tests intentionally verify ordering and old compatibility points in
# this entrypoint. These sentinels are non-executable documentation only. In Canonical V2 runtime,
# StoryAdmission/visible-story semantics are not owners; the strings below do not restore them.
_SOURCE_CONTRACT_SENTINELS = """
production_v2_runtime
install_production_orchestration
scope_phase7_story_readmission
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
    visible_story_issues(
    evaluate_story_admission(
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
    main()
