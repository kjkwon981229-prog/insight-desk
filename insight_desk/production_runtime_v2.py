from __future__ import annotations

"""Execution-scoped installation of Canonical V2 production owners."""

from contextlib import contextmanager
from functools import partial
from types import ModuleType

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
from insight_desk.core import ContractError
from insight_desk.production_canonical_proposition_v2 import (
    resolve_exact_canonical_proposition,
)
from insight_desk.production_event_understanding_lifecycle_v2 import (
    install_event_understanding_lifecycle,
)
from insight_desk.production_event_understanding_resolution_v2 import (
    BoundedEventUnderstandingSourceExpansionLane,
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
from insight_desk.production_relevance_v2 import (
    ConfiguredLiteralRelevanceOwner,
    project_event_relevance,
    rewrite_event_relevance_attempt,
)
from insight_desk.semantic.tooling import KiwiMorphologyHelper


_CORE_HOOKS = (
    "SemanticPipeline",
    "Phase6EventEngine",
    "topic_relevant",
    "relevance_decision",
    "event_topic_relevant",
    "event_understanding_decision",
    "expand_deferred_event_understanding",
    "_attempt",
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
    understanding_resolution_lane = BoundedEventUnderstandingSourceExpansionLane()

    def expand_deferred_event_understanding(*, decision, article, event, facts, topic, discovery):
        return understanding_resolution_lane.expand(
            decision=decision,
            article=article,
            event=event,
            facts=facts,
            topic=topic,
            discovery=discovery,
        )

    registry: ProductionV2Registry | None = None
    try:
        registry = install_production_orchestration(core_module)
        mechanical_attempt = core_module._attempt
        event_understanding_owner = install_event_understanding_lifecycle(core_module, registry)
        identity_resolution_lane = CanonicalIdentityResolutionLane(
            registry,
            event_understanding_owner,
        )
        if hasattr(core_module, "assess_material_event"):
            delattr(core_module, "assess_material_event")
        core_module.relevance_decision = relevance_owner.decide

        def project_canonical_proposition_relevance(*, event, facts, evidence, topic):
            # The source article was prequalified before Event Understanding, but scattered topic
            # terms cannot prove that the selected central event belongs to that topic. Bind the
            # event locally using the one exact canonical proposition and never re-read flat SVO.
            del facts, evidence
            try:
                proposition = resolve_exact_canonical_proposition(registry, event.event_id)
            except ContractError:
                decision = relevance_owner.decide_canonical_proposition(
                    proposition="",
                    canonical_topic=event.topic_id,
                    topic=topic,
                )
            else:
                ref = proposition.ref
                evidence_ref = (
                    f"{ref.source_id}:{ref.field}:{ref.start}:{ref.end}:{ref.text_sha256}"
                )
                decision = relevance_owner.decide_canonical_proposition(
                    proposition=proposition.text,
                    canonical_topic=proposition.event.topic,
                    topic=topic,
                    evidence_refs=(evidence_ref,),
                )
            return project_event_relevance(decision)

        core_module.event_topic_relevant = project_canonical_proposition_relevance

        def project_relevance_attempt(*, topic, query, domain, stage, status, reason=None):
            projected_status, projected_reason = rewrite_event_relevance_attempt(
                stage=stage,
                status=status,
                reason=reason,
            )
            return mechanical_attempt(
                topic=topic,
                query=query,
                domain=domain,
                stage=stage,
                status=projected_status,
                reason=projected_reason,
            )

        core_module._attempt = project_relevance_attempt
        core_module.expand_deferred_event_understanding = expand_deferred_event_understanding
        core_module.Phase6EventEngine = partial(EvidenceIntegrityPhase6EventEngine, registry)
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
