from __future__ import annotations

"""Execution-scoped installation of Canonical V2 production owners."""

from contextlib import contextmanager
from types import ModuleType

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
from insight_desk.production_orchestrator_v2 import (
    ProductionV2Registry,
    install_production_orchestration,
)
from insight_desk.production_phase7_v2 import (
    _ORIGINAL_GENERATION_STORY_ADMISSION,
    _ORIGINAL_PIPELINE_STORY_ADMISSION,
    scope_phase7_story_readmission,
)


_CORE_HOOKS = (
    "SemanticPipeline",
    "topic_relevant",
    "event_topic_relevant",
    "assess_material_event",
    "_visible_topic_headline_bound",
    "visible_story_issues",
    "visible_event_redundant",
    "compare_candidate_identity",
    "judge_same_event_mutual_entailment",
    "resolve_candidate_pair",
    "build_rendered_briefing",
    "build_briefing_view_model",
    "ContractBundle",
    "_write_json",
    "produce_phase7_entry_candidate",
)
_MARKERS = (
    "_INSIGHT_DESK_V2_REGISTRY",
    "_INSIGHT_DESK_V2_IDENTITY_OWNER",
    "_INSIGHT_DESK_V2_AUTHORITATIVE_OWNER",
)
_MISSING = object()


@contextmanager
def production_v2_runtime(core_module: ModuleType):
    """Install V2 authority only while the actual production loop executes.

    Importing ``scripts.phase11_daily_production`` must remain side-effect free for historical
    replay/unit helpers. Production execution receives the V2 owners; every replaced symbol is
    restored even when the run fails.
    """

    hook_snapshot = {name: getattr(core_module, name) for name in _CORE_HOOKS}
    marker_snapshot = {
        name: getattr(core_module, name, _MISSING)
        for name in _MARKERS
    }
    generation_snapshot = generation_module.validate_story_admission
    pipeline_snapshot = generation_pipeline_module.validate_story_admission

    registry: ProductionV2Registry | None = None
    try:
        registry = install_production_orchestration(core_module)
        scope_phase7_story_readmission(core_module)
        yield registry
    finally:
        for name, value in hook_snapshot.items():
            setattr(core_module, name, value)
        for name, value in marker_snapshot.items():
            if value is _MISSING:
                if hasattr(core_module, name):
                    delattr(core_module, name)
            else:
                setattr(core_module, name, value)
        generation_module.validate_story_admission = generation_snapshot
        generation_pipeline_module.validate_story_admission = pipeline_snapshot

        # The ordinary module contract must be restored, not merely any temporary no-op that
        # escaped from a failed installation path.
        if generation_snapshot is _ORIGINAL_GENERATION_STORY_ADMISSION:
            generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
        if pipeline_snapshot is _ORIGINAL_PIPELINE_STORY_ADMISSION:
            generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION
