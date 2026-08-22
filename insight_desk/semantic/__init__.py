"""Evidence-bound semantic extraction and event-engine contracts for the clean-room engine."""

from .evidence import EvidenceSegmenter
from .events import (
    Phase6EventAssessment,
    Phase6EventEngine,
    TemporalAuxiliaryPort,
    TemporalResolution,
    TemporalResolutionSource,
    cited_evidence_text,
    compare_candidate_identity,
    identity_key_from_fact,
    resolve_temporal_state,
)
from .facts import FactDraft, FactExtractionRequest, FactExtractorPort
from .history import (
    EventHistory,
    EventSnapshot,
    StateTransition,
    append_event_snapshot,
    build_event_snapshot,
    derive_state_transitions,
    start_event_history,
)
from .pipeline import SemanticArticleResult, SemanticPipeline

__all__ = [
    "EventHistory",
    "EventSnapshot",
    "EvidenceSegmenter",
    "FactDraft",
    "FactExtractionRequest",
    "FactExtractorPort",
    "Phase6EventAssessment",
    "Phase6EventEngine",
    "SemanticArticleResult",
    "SemanticPipeline",
    "StateTransition",
    "TemporalAuxiliaryPort",
    "TemporalResolution",
    "TemporalResolutionSource",
    "append_event_snapshot",
    "build_event_snapshot",
    "cited_evidence_text",
    "compare_candidate_identity",
    "derive_state_transitions",
    "identity_key_from_fact",
    "resolve_temporal_state",
    "start_event_history",
]
