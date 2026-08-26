from __future__ import annotations

"""Execution-scoped installation of Canonical V2 production owners."""

from contextlib import contextmanager
from types import ModuleType

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
import insight_desk.production_orchestrator_v2 as orchestration_module
from insight_desk.event_understanding_v2 import (
    EventUnderstandingSemanticPipeline,
    PrimaryEventUnderstandingOwner,
)
from insight_desk.production_orchestrator_v2 import (
    ProductionV2Registry,
    install_production_orchestration,
)
from insight_desk.production_phase6_v2 import EvidenceIntegrityPhase6EventEngine
from insight_desk.production_phase7_v2 import (
    _ORIGINAL_GENERATION_STORY_ADMISSION,
    _ORIGINAL_PIPELINE_STORY_ADMISSION,
    scope_phase7_story_readmission,
)


_CORE_HOOKS = (
    "SemanticPipeline",
    "Phase6EventEngine",
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
    "_INSIGHT_DESK_V2_EVENT_UNDERSTANDING_OWNER",
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
    semantic_pipeline_snapshot = orchestration_module.LegacySemanticPipeline

    registry: ProductionV2Registry | None = None
    event_understanding = PrimaryEventUnderstandingOwner()
    try:
        # Event understanding must run before CanonicalEvent creation and authoritative enrichment.
        # The compatibility orchestrator constructs its inner semantic pipeline lazily, so scoping
        # this one dependency here preserves import-time purity and leaves historical helpers alone.
        orchestration_module.LegacySemanticPipeline = lambda *args, **kwargs: (
            EventUnderstandingSemanticPipeline(
                *args,
                owner=event_understanding,
                **kwargs,
            )
        )
        registry = install_production_orchestration(core_module)
        core_module._INSIGHT_DESK_V2_EVENT_UNDERSTANDING_OWNER = event_understanding
        core_module.Phase6EventEngine = EvidenceIntegrityPhase6EventEngine
        scope_phase7_story_readmission(core_module)
        yield registry
    finally:
        orchestration_module.LegacySemanticPipeline = semantic_pipeline_snapshot
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
