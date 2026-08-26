from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from typing import Protocol
from urllib.parse import urlparse

from .models import ArticleCandidate


_URL_DATE_RE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])")


def source_url_has_stale_embedded_date(
    value: str,
    *,
    today: date | None = None,
    max_age_days: int = 3,
) -> bool:
    """Reject only valid stale YYYYMMDD tokens embedded in an article URL path/query.

    This deliberately mirrors the final feed validator's conservative backstop. A URL without a
    valid compact calendar date remains eligible for the normal publication-date checks.
    """

    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    parsed = urlparse(value)
    haystack = f"{parsed.path}?{parsed.query}"
    reference = today if today is not None else datetime.now(timezone.utc).date()
    for match in _URL_DATE_RE.finditer(haystack):
        try:
            candidate = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        if (reference - candidate).days > max_age_days:
            return True
    return False


class NewsDiscoveryRoute(Protocol):
    route_id: str

    def search(
        self,
        query: str,
        *,
        topic_id: str,
        limit: int = 10,
    ) -> tuple[ArticleCandidate, ...]: ...


@dataclass(slots=True)
class StaleUrlFilteringRoute:
    """Drop stale-dated URLs before the discovery aggregator merges route candidates."""

    inner: NewsDiscoveryRoute

    @property
    def route_id(self) -> str:
        return self.inner.route_id

    def search(
        self,
        query: str,
        *,
        topic_id: str,
        limit: int = 10,
    ) -> tuple[ArticleCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.inner.search(query, topic_id=topic_id, limit=limit)
            if not source_url_has_stale_embedded_date(candidate.url)
        )


def with_stale_url_filter(discovery):
    """Wrap every configured route without changing multi-provider aggregation semantics."""

    from .discovery import AggregatedNewsDiscovery

    if not isinstance(discovery, AggregatedNewsDiscovery):
        raise TypeError("stale URL filter requires AggregatedNewsDiscovery")
    return AggregatedNewsDiscovery(
        tuple(StaleUrlFilteringRoute(route) for route in discovery.routes)
    )
