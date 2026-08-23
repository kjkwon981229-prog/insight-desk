from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, urlparse

from insight_desk.api import NaverApiClient
from insight_desk.api.naver import NaverCredentials
from insight_desk.core import FailureKind

from .models import ArticleCandidate, normalize_naver_items


class DiscoveryError(RuntimeError):
    def __init__(self, failure_kind: FailureKind, detail: str) -> None:
        self.failure_kind = failure_kind
        self.detail = detail
        super().__init__(detail)


class DiscoveryConfigError(ValueError):
    """Raised when an optional discovery route is only partially configured."""


class DiscoveryRoute(Protocol):
    route_id: str

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]: ...


def _stable_candidate_id(route_id: str, url: str) -> str:
    import hashlib

    return "article-" + hashlib.sha256(f"{route_id}\x1f{url}".encode("utf-8")).hexdigest()[:20]


def _aware_pubdate(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _validated_http_url(value: str) -> str | None:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


@dataclass(slots=True)
class NaverNewsDiscovery:
    client: NaverApiClient
    route_id: str = "naver_search"

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        try:
            payload = self.client.search_news(query, display=min(max(limit, 1), 100), start=1, sort="date")
        except Exception as exc:
            raise DiscoveryError(FailureKind.TRANSIENT_PROVIDER, f"NAVER search failed:{type(exc).__name__}") from exc
        primary = normalize_naver_items(payload, topic_id=topic_id, query=query)
        raw_items = payload.get("items", [])
        raw_by_original: dict[str, dict[str, Any]] = {}
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                original = str(raw.get("originallink") or raw.get("link") or "").strip()
                if original:
                    raw_by_original[original] = raw

        output: list[ArticleCandidate] = []
        for candidate in primary:
            output.append(candidate)
            raw = raw_by_original.get(candidate.url)
            if raw is None:
                continue
            alternate = _validated_http_url(str(raw.get("link") or ""))
            if not alternate or alternate == candidate.url:
                continue
            parsed = urlparse(alternate)
            output.append(
                ArticleCandidate(
                    candidate_id=candidate.candidate_id + "-alt",
                    url=alternate,
                    search_title=candidate.search_title,
                    source_name=(parsed.hostname or parsed.netloc).lower(),
                    published_at=candidate.published_at,
                    topic_ids=candidate.topic_ids,
                    query=query,
                    retrieved_via="naver_search_alternate_link",
                )
            )
        return tuple(output)


@dataclass(slots=True)
class BingNewsRssDiscovery:
    opener: Callable[..., Any] = urllib.request.urlopen
    timeout: float = 12.0
    route_id: str = "bing_news_rss"

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        params = urllib.parse.urlencode(
            {"q": f"{query} loc:KR", "qft": 'sortbydate="1"', "format": "RSS"}
        )
        url = "https://www.bing.com/news/search?" + params
        request = urllib.request.Request(url, headers={"User-Agent": "InsightDesk/1.0"})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise DiscoveryError(FailureKind.TRANSIENT_PROVIDER, f"Bing RSS failed:{type(exc).__name__}") from exc
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise DiscoveryError(FailureKind.INVALID_OUTPUT, "Bing RSS is invalid XML") from exc

        output: list[ArticleCandidate] = []
        seen: set[str] = set()
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = self._publisher_url(item.findtext("link") or "")
            if not title or not link or link in seen:
                continue
            parsed = urlparse(link)
            output.append(
                ArticleCandidate(
                    candidate_id=_stable_candidate_id(self.route_id, link),
                    url=link,
                    search_title=title,
                    source_name=(parsed.hostname or parsed.netloc).lower(),
                    published_at=_aware_pubdate(item.findtext("pubDate") or ""),
                    topic_ids=(topic_id,),
                    query=query,
                    retrieved_via=self.route_id,
                )
            )
            seen.add(link)
            if len(output) >= limit:
                break
        return tuple(output)

    @staticmethod
    def _publisher_url(value: str) -> str | None:
        url = _validated_http_url(value)
        if not url:
            return None
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in {"bing.com", "www.bing.com"} and parsed.path.casefold().endswith("/news/apiclick.aspx"):
            target = parse_qs(parsed.query).get("url", [""])[0]
            return _validated_http_url(target)
        return url


@dataclass(slots=True)
class GdeltDocDiscovery:
    opener: Callable[..., Any] = urllib.request.urlopen
    timeout: float = 12.0
    route_id: str = "gdelt_doc"

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        params = urllib.parse.urlencode(
            {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": min(max(limit, 1), 250),
                "timespan": "3days",
                "sort": "datedesc",
            }
        )
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + params
        request = urllib.request.Request(url, headers={"User-Agent": "InsightDesk/1.0"})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise DiscoveryError(FailureKind.TRANSIENT_PROVIDER, f"GDELT DOC failed:{type(exc).__name__}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DiscoveryError(FailureKind.INVALID_OUTPUT, "GDELT DOC is invalid JSON") from exc
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        if not isinstance(articles, list):
            raise DiscoveryError(FailureKind.INVALID_OUTPUT, "GDELT articles must be a list")

        output: list[ArticleCandidate] = []
        seen: set[str] = set()
        for raw_item in articles:
            if not isinstance(raw_item, dict):
                continue
            link = _validated_http_url(str(raw_item.get("url") or ""))
            title = str(raw_item.get("title") or "").strip()
            if not link or not title or link in seen:
                continue
            parsed = urlparse(link)
            output.append(
                ArticleCandidate(
                    candidate_id=_stable_candidate_id(self.route_id, link),
                    url=link,
                    search_title=title,
                    source_name=str(raw_item.get("domain") or parsed.hostname or parsed.netloc).lower(),
                    published_at=_aware_pubdate(str(raw_item.get("seendate") or "")),
                    topic_ids=(topic_id,),
                    query=query,
                    retrieved_via=self.route_id,
                )
            )
            seen.add(link)
            if len(output) >= limit:
                break
        return tuple(output)


@dataclass(slots=True)
class SequentialNewsDiscovery:
    routes: tuple[DiscoveryRoute, ...]
    _route_stats: dict[str, dict[str, int]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.routes) < 1:
            raise ValueError("at least one discovery route is required")
        ids = [route.route_id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("discovery route ids must be unique")
        self._route_stats = {
            route_id: {"calls": 0, "errors": 0, "empty": 0, "selected": 0, "candidates": 0}
            for route_id in ids
        }

    @property
    def route_stats(self) -> dict[str, dict[str, int]]:
        return {route_id: dict(stats) for route_id, stats in self._route_stats.items()}

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        last_error: DiscoveryError | None = None
        for route in self.routes:
            stats = self._route_stats[route.route_id]
            stats["calls"] += 1
            try:
                candidates = route.search(query, topic_id=topic_id, limit=limit)
            except DiscoveryError as exc:
                stats["errors"] += 1
                last_error = exc
                continue
            if candidates:
                stats["selected"] += 1
                stats["candidates"] += len(candidates)
                return candidates
            stats["empty"] += 1
        if last_error is not None:
            raise last_error
        return ()


def default_news_discovery(*, env: dict[str, str] | None = None) -> SequentialNewsDiscovery:
    source = dict(os.environ) if env is None else env
    client_id = str(source.get("NCP_CLIENT_ID", "")).strip()
    client_secret = str(source.get("NCP_CLIENT_SECRET", "")).strip()
    if bool(client_id) != bool(client_secret):
        raise DiscoveryConfigError(
            "NAVER discovery credentials must provide both NCP_CLIENT_ID and NCP_CLIENT_SECRET"
        )

    routes: list[DiscoveryRoute] = []
    if client_id and client_secret:
        routes.append(
            NaverNewsDiscovery(
                NaverApiClient(NaverCredentials(client_id=client_id, client_secret=client_secret))
            )
        )
    routes.extend((BingNewsRssDiscovery(), GdeltDocDiscovery()))
    return SequentialNewsDiscovery(tuple(routes))
