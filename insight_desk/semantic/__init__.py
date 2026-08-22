"""Evidence-bound semantic extraction contracts for the clean-room engine."""

from .evidence import EvidenceSegmenter
from .facts import FactDraft, FactExtractionRequest, FactExtractorPort
from .pipeline import SemanticArticleResult, SemanticPipeline

__all__ = [
    "EvidenceSegmenter",
    "FactDraft",
    "FactExtractionRequest",
    "FactExtractorPort",
    "SemanticArticleResult",
    "SemanticPipeline",
]
