from __future__ import annotations

"""Execution-scoped installation of Canonical V2 production owners."""

from contextlib import contextmanager
from types import ModuleType

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
from insight_desk.production_article_understanding_v2 import (
    install_article_understanding_semantic_pipeline,
)
from insight_desk.production_identity_resolution_v2 import CanonicalIdentityResolutionLane
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
from insight_desk.production_relevance_v2 import ConfiguredLiteralRelevanceOwner
from insight_desk.semantic.tooling import KiwiMorphologyHelper


_CORE_HOOKS = (
    "SemanticPipeline",
    "Phase6EventEngine",
    "topic_relevant",
    "relevance_decision",
    "event_topic_relevant",
    "_visible_topic_headline_bound",
    "visible_story_issues",
    "visible_event_redundant",
    "compare_candidate_identity",
    "judge_same_event_mutual_entailment",
    "resolve_candidate_pair",
    "resolve_deferred_identity",
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


def _optional_morphology():
    try:
        return KiwiMorphologyHelper()
    except RuntimeError:
        return None


@contextmanager
def production_v2_runtime(core_module: ModuleType):
    """Install V2 authority only while the actual production loop executes."""

    hook_snapshot = {name: getattr(core_module, name, _MISSING) for name in _CORE_HOOKS}
    marker_snapshot = {name: getattr(core_module, name, _MISSING) for name in _MARKERS}
    generation_snapshot = generation_module.validate_story_admission
    pipeline_snapshot = generation_pipeline_module.validate_story_admission
    relevance_owner = ConfiguredLiteralRelevanceOwner(
        core_module.topic_relevant,
        morphology=_optional_morphology(),
    )

    registry: ProductionV2Registry | None = None
    try:
        registry = install_production_orchestration(core_module)
        install_article_understanding_semantic_pipeline(core_module)
        identity_resolution_lane = CanonicalIdentityResolutionLane(registry)
        if hasattr(core_module, "assess_material_event"):
            delattr(core_module, "assess_material_event")
        core_module.relevance_decision = relevance_owner.decide
        core_module.event_topic_relevant = lambda *, event, facts, evidence, topic: (
            relevance_owner.decide_event(event=event, facts=facts, topic=topic).is_relevant
        )
        core_module.Phase6EventEngine = EvidenceIntegrityPhase6EventEngine
        core_module.resolve_deferred_identity = identity_resolution_lane.resolve
        scope_phase7_story_readmission(core_module, registry)
        yield registry
    finally:
        for name, value in hook_snapshot.items():
            if value is _MISSING:
                if hasattr(core_module, name):
                    delattr(core_module, name)
            else:
                setattr(core_module, name, value)
        if hasattr(core_module, "assess_material_event"):
            delattr(core_module, "assess_material_event")
        for name, value in marker_snapshot.items():
            if value is _MISSING:
                if hasattr(core_module, name):
                    delattr(core_module, name)
            else:
                setattr(core_module, name, value)
        generation_module.validate_story_admission = generation_snapshot
        generation_pipeline_module.validate_story_admission = pipeline_snapshot

        if generation_snapshot is _ORIGINAL_GENERATION_STORY_ADMISSION:
            generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
        if pipeline_snapshot is _ORIGINAL_PIPELINE_STORY_ADMISSION:
            generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION
