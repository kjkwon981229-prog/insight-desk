"""Evidence-preserving acquisition for web articles and official structured sources."""

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
from .official import (
    normalize_ecos_statistics,
    normalize_kosis_statistics,
    normalize_opendart_filings,
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
    "normalize_ecos_statistics",
    "normalize_kosis_statistics",
    "normalize_naver_items",
    "normalize_opendart_filings",
]
