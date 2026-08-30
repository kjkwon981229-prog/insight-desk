from __future__ import annotations

"""Production-scoped Phase 6 bridge after Canonical Identity resolution.

Production Phase 6 is no longer an identity or temporal-semantic owner. Canonical Identity has
already resolved or deferred the event before this bridge runs, and Event Understanding has already
promoted the semantic event into ``CanonicalEvent``. Legacy ``CandidateEvent``/``EventFact`` objects
remain only for provenance and the mechanical evidence-integrity check required by the compatibility
loop.
"""

from typing import Mapping, Protocol

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    ContractError,
    EvidenceSpan,
    EventFact,
    SelectionSignals,
    decide_selection,
)
from insight_desk.production_identity_core_v2 import _identity_key as canonical_identity_key
from insight_desk.production_orchestrator_v2 import _evidence_integrity_assessment
from insight_desk.semantic.events import (
    Phase6AutoMaterialAssessment,
    Phase6EventAssessment,
    Phase6EventEngine,
    Phase6SelectionContext,
    TemporalAuxiliaryPort,
    TemporalResolution,
    TemporalResolutionSource,
)


class CanonicalEventRegistry(Protocol):
    def canonical_event(self, event_id: str) -> CanonicalEvent: ...


class EvidenceIntegrityPhase6EventEngine(Phase6EventEngine):
    """Mechanical selection/material bridge projected from the already-canonical event."""

    def __init__(self, registry: CanonicalEventRegistry) -> None:
        self.registry = registry

    def assess_with_auto_material(
        self,
        event: CandidateEvent,
        *,
        facts: Mapping[str, EventFact],
        evidence: Mapping[str, EvidenceSpan],
        selection_context: Phase6SelectionContext,
        temporal_auxiliary: TemporalAuxiliaryPort | None = None,
    ) -> Phase6AutoMaterialAssessment:
        # The production Event Understanding + Canonical Identity stages already own semantic event
        # state. Phase 6 must not re-read evidence to form a second identity/temporal opinion.
        del temporal_auxiliary
        if len(event.fact_ids) != 1:
            raise ContractError("production Phase6 requires one pre-publication fact lineage")

        canonical = self.registry.canonical_event(event.event_id)
        if canonical.topic != event.topic_id:
            raise ContractError(f"{event.event_id}: CandidateEvent/CanonicalEvent topic mismatch")

        material = _evidence_integrity_assessment(
            event,
            facts=facts,
            evidence=evidence,
        )
        selection = decide_selection(
            SelectionSignals(
                topic_relevant=selection_context.topic_relevant,
                material_event=material.selection_signal,
                fresh=selection_context.fresh,
                source_usable=selection_context.source_usable,
                identity_resolved=selection_context.identity_resolved,
            )
        )

        if canonical.temporal_state is None:
            temporal = TemporalResolution(
                fact_id=event.fact_ids[0],
                state=None,
                source=TemporalResolutionSource.UNRESOLVED,
                auxiliary_used=False,
                error_code="canonical_temporal_state_missing",
            )
        else:
            # The current compatibility Event Understanding promotion preserves the extractor-origin
            # temporal state in CanonicalEvent. Preserve that provenance; do not resolve it again.
            temporal = TemporalResolution(
                fact_id=event.fact_ids[0],
                state=canonical.temporal_state,
                source=TemporalResolutionSource.EXTRACTED,
                auxiliary_used=False,
            )

        event_assessment = Phase6EventAssessment(
            event=event,
            identity_keys=(canonical_identity_key(canonical),),
            temporal=(temporal,),
            selection=selection,
        )
        return Phase6AutoMaterialAssessment(
            material=material,
            event_assessment=event_assessment,
        )
