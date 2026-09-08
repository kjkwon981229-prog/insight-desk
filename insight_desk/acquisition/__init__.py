"""Evidence-preserving acquisition for web articles and official structured sources."""

from .discovery import (
    AggregatedNewsDiscovery,
    BingNewsRssDiscovery,
    DiscoveryConfigError,
    DiscoveryError,
    GdeltDocDiscovery,
    NaverNewsDiscovery,
    SequentialNewsDiscovery,
    default_news_discovery as _default_news_discovery,
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
from .source_quality import source_url_has_stale_embedded_date, with_stale_url_filter


def default_news_discovery(*, env: dict[str, str] | None = None) -> AggregatedNewsDiscovery:
    """Return the configured multi-provider discovery stack with stale URLs filtered per route."""

    return with_stale_url_filter(_default_news_discovery(env=env))


__all__ = [
    "AcquisitionError",
    "AcquisitionPipeline",
    "AcquisitionResult",
    "AggregatedNewsDiscovery",
    "ArticleCandidate",
    "ArticleMainTextExtractor",
    "BingNewsRssDiscovery",
    "DiscoveryConfigError",
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
    "source_url_has_stale_embedded_date",
]
