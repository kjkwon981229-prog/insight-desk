"""Evidence-preserving acquisition for web articles and official structured sources."""

from .discovery import (
    BingNewsRssDiscovery,
    DiscoveryError,
    GdeltDocDiscovery,
    NaverNewsDiscovery,
    SequentialNewsDiscovery,
    default_news_discovery,
)
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
from .runtime import (
    ArticleMainTextExtractor,
    PlaywrightHtmlRenderer,
    TrafilaturaExtractor,
    UrlLibHtmlFetcher,
)

__all__ = [
    "AcquisitionError",
    "AcquisitionPipeline",
    "AcquisitionResult",
    "ArticleCandidate",
    "ArticleMainTextExtractor",
    "BingNewsRssDiscovery",
    "DiscoveryError",
    "ExtractedArticle",
    "ExtractionQuality",
    "ExtractionQualityPolicy",
    "FetchedPage",
    "GdeltDocDiscovery",
    "NaverNewsDiscovery",
    "PlaywrightHtmlRenderer",
    "SequentialNewsDiscovery",
    "TrafilaturaExtractor",
    "UrlLibHtmlFetcher",
    "default_news_discovery",
    "normalize_ecos_statistics",
    "normalize_kosis_statistics",
    "normalize_naver_items",
    "normalize_opendart_filings",
]
