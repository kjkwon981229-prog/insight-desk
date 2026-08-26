from __future__ import annotations

"""Production-scoped Phase 6 bridge for Canonical V2 ownership.

The legacy ``Phase6EventEngine.assess_with_auto_material`` calls the semantic-material helper
captured inside ``insight_desk.semantic.events``. Replacing only the production core's
``assess_material_event`` hook therefore leaves a second semantic material authority reachable.
This bridge keeps Phase 6 identity/temporal/selection mechanics but feeds them the single V2
mechanical evidence-integrity assessment already owned by the production orchestrator.
"""

from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, SelectionSignals
from insight_desk.production_orchestrator_v2 import _evidence_integrity_assessment
from insight_desk.semantic.events import (
    Phase6AutoMaterialAssessment,
    Phase6EventEngine,
    Phase6SelectionContext,
    TemporalAuxiliaryPort,
)


class EvidenceIntegrityPhase6EventEngine(Phase6EventEngine):
    """Phase 6 mechanics with no independent semantic material-event reclassification."""

    def assess_with_auto_material(
        self,
        event: CandidateEvent,
        *,
        facts: Mapping[str, EventFact],
        evidence: Mapping[str, EvidenceSpan],
        selection_context: Phase6SelectionContext,
        temporal_auxiliary: TemporalAuxiliaryPort | None = None,
    ) -> Phase6AutoMaterialAssessment:
        material = _evidence_integrity_assessment(
            event,
            facts=facts,
            evidence=evidence,
        )
        event_assessment = self.assess(
            event,
            facts=facts,
            evidence=evidence,
            selection_signals=SelectionSignals(
                topic_relevant=selection_context.topic_relevant,
                material_event=material.selection_signal,
                fresh=selection_context.fresh,
                source_usable=selection_context.source_usable,
                identity_resolved=selection_context.identity_resolved,
            ),
            temporal_auxiliary=temporal_auxiliary,
        )
        return Phase6AutoMaterialAssessment(
            material=material,
            event_assessment=event_assessment,
        )
