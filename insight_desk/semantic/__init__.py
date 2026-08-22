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
from .pipeline import SemanticArticleResult, SemanticPipeline

__all__ = [
    "EvidenceSegmenter",
    "FactDraft",
    "FactExtractionRequest",
    "FactExtractorPort",
    "Phase6EventAssessment",
    "Phase6EventEngine",
    "SemanticArticleResult",
    "SemanticPipeline",
    "TemporalAuxiliaryPort",
    "TemporalResolution",
    "TemporalResolutionSource",
    "cited_evidence_text",
    "compare_candidate_identity",
    "identity_key_from_fact",
    "resolve_temporal_state",
]
