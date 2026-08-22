"""Evidence-preserving article acquisition for Insight Desk."""

from .models import (
    AcquisitionError,
    AcquisitionResult,
    ArticleCandidate,
    ExtractedArticle,
    ExtractionQuality,
    ExtractionQualityPolicy,
    FetchedPage,
    normalize_naver_items,
)
from .pipeline import AcquisitionPipeline
from .runtime import PlaywrightHtmlRenderer, TrafilaturaExtractor, UrlLibHtmlFetcher

__all__ = [
    "AcquisitionError",
    "AcquisitionPipeline",
    "AcquisitionResult",
    "ArticleCandidate",
    "ExtractedArticle",
    "ExtractionQuality",
    "ExtractionQualityPolicy",
    "FetchedPage",
    "PlaywrightHtmlRenderer",
    "TrafilaturaExtractor",
    "UrlLibHtmlFetcher",
    "normalize_naver_items",
]
