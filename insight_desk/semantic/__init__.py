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
    detect_explicit_temporal_state,
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
from .identity import IdentityResolution, merge_candidate_events, resolve_candidate_pair
from .pipeline import SemanticArticleResult, SemanticPipeline
from .tooling import (
    AliasCandidate,
    KiwiMorphologyHelper,
    MorphologyToken,
    RapidFuzzAliasRetriever,
    SentenceSpan,
)

__all__ = [
    "AliasCandidate",
    "EventHistory",
    "EventSnapshot",
    "EvidenceSegmenter",
    "FactDraft",
    "FactExtractionRequest",
    "FactExtractorPort",
    "IdentityResolution",
    "KiwiMorphologyHelper",
    "MorphologyToken",
    "Phase6EventAssessment",
    "Phase6EventEngine",
    "RapidFuzzAliasRetriever",
    "SemanticArticleResult",
    "SemanticPipeline",
    "SentenceSpan",
    "StateTransition",
    "TemporalAuxiliaryPort",
    "TemporalResolution",
    "TemporalResolutionSource",
    "append_event_snapshot",
    "build_event_snapshot",
    "cited_evidence_text",
    "compare_candidate_identity",
    "derive_state_transitions",
    "detect_explicit_temporal_state",
    "identity_key_from_fact",
    "merge_candidate_events",
    "resolve_candidate_pair",
    "resolve_temporal_state",
    "start_event_history",
]
