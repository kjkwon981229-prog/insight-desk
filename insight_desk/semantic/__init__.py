"""Evidence-bound semantic extraction contracts for the clean-room engine."""

from .evidence import EvidenceSegmenter
from .facts import FactDraft, FactExtractionRequest, FactExtractorPort
from .groq_extractor import FACT_EXTRACTION_SCHEMA, Groq20BFactExtractor
from .pipeline import SemanticArticleResult, SemanticPipeline

__all__ = [
    "EvidenceSegmenter",
    "FACT_EXTRACTION_SCHEMA",
    "FactDraft",
    "FactExtractionRequest",
    "FactExtractorPort",
    "Groq20BFactExtractor",
    "SemanticArticleResult",
    "SemanticPipeline",
]
