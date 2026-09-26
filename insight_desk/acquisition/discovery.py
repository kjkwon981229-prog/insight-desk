from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Protocol, cast
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit

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


_MPM_ORIGIN = "https://www.mpm.go.kr"
_MPM_HOST = urllib.parse.urlsplit(_MPM_ORIGIN).hostname
_MPM_BOARD_PATHS = {
    "/mpm/comm/newsPress/newsPressRelease/",
    "/mpm/comm/newsInnoNotice/",
}
_PSAT_EXAM_TITLES = (
    "PSAT", "공직적격성평가", "공채", "공개경쟁채용시험", "외교관후보자",
    "민간경력자", "국가공무원 채용", "공무원 시험",
)
_MPM_DATE = re.compile(r"\b20\d{2}-(?:0[1-9]|1[0-2])-(?:[0-2]\d|3[01])\b")
_KST = timezone(timedelta(hours=9))


def _mpm_article_url(board_url: str, href: str) -> str | None:
    """Accept a real MPM detail link, never an off-site or synthetic board entry."""
    url = urllib.parse.urljoin(board_url, href)
    parsed = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(parsed.query)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _MPM_HOST
        or parsed.path not in _MPM_BOARD_PATHS
        or params.get("mode") != ["view"]
        or not any(value.isdecimal() for value in params.get("cntId", ()))
    ):
        return None
    return url


class _MpmBoardRows(HTMLParser):
    """Read only linked article titles and the same row's publication date."""

    def __init__(self, board_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.board_url = board_url
        self.items: list[tuple[str, str, datetime]] = []
        self.rows_seen = 0
        self._in_row = False
        self._in_cell = False
        self._link: str | None = None
        self._link_text: list[str] = []
        self._cell_text: list[str] = []
        self._row_text: list[str] = []
        self._row_links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._in_row = True
            self._row_text = []
            self._row_links = []
        elif self._in_row and tag == "td":
            self._in_cell = True
            self._cell_text = []
        elif self._in_cell and tag == "a":
            self._link = dict(attrs).get("href")
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)
        if self._link is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link is not None:
            title = " ".join(" ".join(self._link_text).split())
            link = _mpm_article_url(self.board_url, self._link)
            if title and link:
                self._row_links.append((title, link))
            self._link = None
        elif tag == "td" and self._in_cell:
            self._row_text.append(" ".join(self._cell_text))
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if self._row_text:
                self.rows_seen += 1
            match = _MPM_DATE.search(" ".join(self._row_text))
            if match and self._row_links:
                try:
                    published = datetime.combine(
                        datetime.strptime(match.group(), "%Y-%m-%d").date(), time.min, _KST
                    )
                except ValueError:
                    published = None
                if published is not None:
                    title, url = self._row_links[0]
                    self.items.append((title, url, published))
            self._in_row = False


@dataclass(slots=True)
class MpmOfficialBoardDiscovery:
    """Primary-source candidate lane for PSAT/civil-service notices and releases.

    The title only nominates an official page. The ordinary acquisition, source relevance,
    event understanding, identity and verification gates still decide publication.
    """

    board_url: str
    route_id: str
    max_pages: int = 2
    opener: Callable[..., Any] = urllib.request.urlopen
    timeout: float = 12.0
    _cached: tuple[tuple[str, str, datetime], ...] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.board_url)
        if parsed.scheme != "https" or parsed.hostname != _MPM_HOST or parsed.path not in _MPM_BOARD_PATHS:
            raise DiscoveryConfigError("MPM official board URL must be an allowlisted HTTPS board")
        if not 1 <= self.max_pages <= 3:
            raise DiscoveryConfigError("MPM official board page budget must be between 1 and 3")

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        if topic_id != "psat_recruitment":
            return ()
        if self._cached is None:
            rows: list[tuple[str, str, datetime]] = []
            for page in range(1, self.max_pages + 1):
                url = self.board_url + "?" + urllib.parse.urlencode({"pageIdx": page})
                request = urllib.request.Request(url, headers={"User-Agent": "InsightDesk/1.0"})
                try:
                    with self.opener(request, timeout=self.timeout) as response:
                        raw = response.read()
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                    if rows:  # Preserve already-proven first-page source links on a later-page miss.
                        break
                    raise DiscoveryError(
                        FailureKind.TRANSIENT_PROVIDER, f"MPM board failed:{type(exc).__name__}"
                    ) from exc
                parser = _MpmBoardRows(self.board_url)
                parser.feed(raw.decode("utf-8", errors="replace"))
                if not parser.rows_seen or not parser.items:
                    if rows:
                        break
                    raise DiscoveryError(FailureKind.INVALID_OUTPUT, "MPM board has no linked dated articles")
                rows.extend(parser.items)
            self._cached = tuple(dict.fromkeys(rows))
        now = datetime.now(timezone.utc)
        return tuple(
            ArticleCandidate(
                candidate_id=_stable_candidate_id(self.route_id, url),
                url=url,
                search_title=title,
                source_name="인사혁신처",
                published_at=published,
                topic_ids=(topic_id,),
                query=query,
                retrieved_via=self.route_id,
            )
            for title, url, published in self._cached
            if any(anchor.casefold() in title.casefold() for anchor in _PSAT_EXAM_TITLES)
            and -timedelta(hours=6) <= now - published.astimezone(timezone.utc) <= timedelta(hours=72)
        )[:limit]


def _configured_mpm_routes(config_path: Path | None = None) -> list[DiscoveryRoute]:
    path = config_path or Path(__file__).resolve().parents[2] / "config" / "authoritative_sources.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiscoveryConfigError("official source discovery config is unavailable or invalid") from exc
    routes: list[DiscoveryRoute] = []
    for source in config.get("public_sources", []):
        if source.get("discovery_mode") != "mpm_board":
            continue
        if source.get("topic_ids") != ["psat_recruitment"]:
            raise DiscoveryConfigError("MPM official board must only feed the PSAT topic")
        routes.append(MpmOfficialBoardDiscovery(
            board_url=str(source["url"]),
            route_id=str(source["id"]),
            max_pages=int(source.get("max_requests", 2)),
        ))
    return routes


def _stable_candidate_id(route_id: str, url: str) -> str:
    import hashlib

    return "article-" + hashlib.sha256(f"{route_id}\x1f{url}".encode("utf-8")).hexdigest()[:20]


def _alternate_candidate_id(parent_candidate_id: str, alternate_url: str) -> str:
    """Give every alternate document URL its own immutable article identity.

    A NAVER result can return the same publisher URL with different NAVER alternate URLs across
    queries.  Reusing ``<publisher-id>-alt`` for all of them makes distinct SourceDocuments share
    one article id and can abort the whole production run at the provenance boundary.  Keep the
    publisher candidate prefix for duplicate grouping, while binding the article id to the exact
    alternate URL that will be fetched.
    """

    import hashlib

    digest = hashlib.sha256(alternate_url.strip().encode("utf-8")).hexdigest()[:16]
    return f"{parent_candidate_id}-alt-{digest}"


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


def _mechanical_url_key(value: str) -> str:
    """Normalize only transport-level URL syntax for cross-provider duplicate suppression.

    Discovery is not allowed to infer event identity. We therefore keep path/query bytes intact,
    remove only a fragment that is never sent to the publisher, and normalize scheme/host casing
    plus default ports. Tracking-parameter heuristics and headline similarity are intentionally
    absent.
    """

    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    port = parsed.port
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


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
                    candidate_id=_alternate_candidate_id(candidate.candidate_id, alternate),
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
class AggregatedNewsDiscovery:
    """Collect candidates from every healthy route, then mechanically merge them.

    Route order is priority order, not failover order. The final queue is round-robin across every
    configured route so one provider cannot monopolize the production acquisition budget merely
    because it returned first. A route that repeatedly fails is isolated for the remainder of the
    run; the failure never becomes a semantic decision about another route's candidates.
    """

    routes: tuple[DiscoveryRoute, ...]
    max_consecutive_errors: int = 2
    _route_stats: dict[str, dict[str, object]] = field(init=False, repr=False)
    _consecutive_errors: dict[str, int] = field(init=False, repr=False)
    _open_routes: set[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.routes) < 1:
            raise ValueError("at least one discovery route is required")
        ids = [route.route_id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("discovery route ids must be unique")
        if self.max_consecutive_errors < 1:
            raise ValueError("max_consecutive_errors must be positive")
        self._route_stats = {
            route_id: {
                "calls": 0,
                "errors": 0,
                "empty": 0,
                "selected": 0,
                "candidates": 0,
                "contributed": 0,
                "circuit_skips": 0,
                "state": "healthy",
                "last_error_kind": None,
                "error_kinds": {},
            }
            for route_id in ids
        }
        self._consecutive_errors = {route_id: 0 for route_id in ids}
        self._open_routes = set()

    @property
    def route_stats(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for route_id, stats in self._route_stats.items():
            copied = dict(stats)
            copied["error_kinds"] = dict(cast(dict[str, int], stats["error_kinds"]))
            snapshot[route_id] = copied
        return snapshot

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        if limit < 1:
            raise ValueError("discovery limit must be positive")

        route_results: list[tuple[DiscoveryRoute, tuple[ArticleCandidate, ...]]] = []
        last_error: DiscoveryError | None = None
        for route in self.routes:
            stats = self._route_stats[route.route_id]
            if route.route_id in self._open_routes:
                stats["circuit_skips"] = int(stats["circuit_skips"]) + 1
                route_results.append((route, ()))
                continue
            stats["calls"] = int(stats["calls"]) + 1
            try:
                candidates = route.search(query, topic_id=topic_id, limit=limit)
            except DiscoveryError as exc:
                stats["errors"] = int(stats["errors"]) + 1
                error_kind = exc.failure_kind.value
                error_kinds = cast(dict[str, int], stats["error_kinds"])
                error_kinds[error_kind] = int(error_kinds.get(error_kind, 0)) + 1
                stats["last_error_kind"] = error_kind
                consecutive = self._consecutive_errors[route.route_id] + 1
                self._consecutive_errors[route.route_id] = consecutive
                if consecutive >= self.max_consecutive_errors:
                    self._open_routes.add(route.route_id)
                    stats["state"] = "open"
                last_error = exc
                route_results.append((route, ()))
                continue
            self._consecutive_errors[route.route_id] = 0
            stats["state"] = "healthy"
            stats["last_error_kind"] = None
            stats["candidates"] = int(stats["candidates"]) + len(candidates)
            if not candidates:
                stats["empty"] = int(stats["empty"]) + 1
            route_results.append((route, candidates))

        output: list[ArticleCandidate] = []
        seen_urls: set[str] = set()
        contributed: dict[str, int] = {route.route_id: 0 for route in self.routes}
        max_depth = max((len(candidates) for _, candidates in route_results), default=0)
        for index in range(max_depth):
            for route, candidates in route_results:
                if index >= len(candidates):
                    continue
                candidate = candidates[index]
                url_key = _mechanical_url_key(candidate.url)
                if url_key in seen_urls:
                    continue
                seen_urls.add(url_key)
                output.append(candidate)
                contributed[route.route_id] += 1
                if len(output) >= limit:
                    break
            if len(output) >= limit:
                break

        for route_id, count in contributed.items():
            if count:
                stats = self._route_stats[route_id]
                stats["selected"] = int(stats["selected"]) + 1
                stats["contributed"] = int(stats["contributed"]) + count

        if output:
            return tuple(output)
        if last_error is not None:
            raise last_error
        return ()


# Compatibility name retained for historical imports. The production semantics are aggregation,
# not first-success failover.
SequentialNewsDiscovery = AggregatedNewsDiscovery


def default_news_discovery(*, env: dict[str, str] | None = None) -> AggregatedNewsDiscovery:
    source = dict(os.environ) if env is None else env
    client_id = str(source.get("NCP_CLIENT_ID", "")).strip()
    client_secret = str(source.get("NCP_CLIENT_SECRET", "")).strip()
    if bool(client_id) != bool(client_secret):
        raise DiscoveryConfigError(
            "NAVER discovery credentials must provide both NCP_CLIENT_ID and NCP_CLIENT_SECRET"
        )

    gdelt_flag = str(source.get("GDELT_DISCOVERY_ENABLED", "false")).strip().casefold()
    if gdelt_flag not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise DiscoveryConfigError("GDELT_DISCOVERY_ENABLED must be an explicit boolean")
    gdelt_enabled = gdelt_flag in {"true", "1", "yes", "on"}

    routes: list[DiscoveryRoute] = _configured_mpm_routes()
    if client_id and client_secret:
        routes.append(
            NaverNewsDiscovery(
                NaverApiClient(NaverCredentials(client_id=client_id, client_secret=client_secret))
            )
        )
    routes.append(BingNewsRssDiscovery())
    if gdelt_enabled:
        routes.append(GdeltDocDiscovery())
    return AggregatedNewsDiscovery(tuple(routes))
