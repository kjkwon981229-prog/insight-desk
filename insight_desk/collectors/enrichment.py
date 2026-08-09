from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from urllib.parse import urlsplit

from ..domain.models import EvidenceType, NewsItem
from ..pipeline.normalization import normalize_url, parse_datetime
from .cache import ResponseCache
from .transport import Transport, UrlLibTransport


_CHARSET_RE = re.compile(r"charset\s*=\s*[\"']?([\w.-]+)", re.IGNORECASE)
_META_KEYS = {
    "og:title",
    "og:description",
    "og:site_name",
    "article:published_time",
    "article:modified_time",
    "description",
    "application-name",
    "publisher",
    "date",
    "datepublished",
    "datemodified",
    "pubdate",
}


@dataclass(frozen=True)
class MetadataResult:
    url: str
    title: str = ""
    description: str = ""
    canonical_url: str = ""
    publisher: str = ""
    published_at: str | None = None
    modified_at: str | None = None
    reason: str = ""

    @property
    def success(self) -> bool:
        return bool(
            self.title
            or self.description
            or self.canonical_url
            or self.publisher
            or self.published_at
            or self.modified_at
        )

    def to_cache_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "canonical_url": self.canonical_url,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "modified_at": self.modified_at,
            "reason": self.reason,
        }

    @classmethod
    def from_cache_payload(cls, url: str, payload: dict[str, object]) -> "MetadataResult":
        return cls(
            url=url,
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            canonical_url=str(payload.get("canonical_url") or ""),
            publisher=str(payload.get("publisher") or ""),
            published_at=str(payload["published_at"]) if payload.get("published_at") else None,
            modified_at=str(payload["modified_at"]) if payload.get("modified_at") else None,
            reason=str(payload.get("reason") or ""),
        )


@dataclass(frozen=True)
class EnrichmentReport:
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    reasons: tuple[str, ...] = ()


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document_title = ""
        self.canonical = ""
        self.meta: dict[str, str] = {}
        self._inside_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        tag_name = tag.lower()
        if tag_name == "title":
            self._inside_title = True
        elif tag_name == "meta":
            key = (values.get("property") or values.get("name") or values.get("itemprop") or "").lower()
            content = values.get("content", "").strip()
            if key in _META_KEYS and content and key not in self.meta:
                self.meta[key] = content
        elif tag_name == "link":
            rel = {part.lower() for part in values.get("rel", "").split()}
            href = values.get("href", "").strip()
            if "canonical" in rel and href and not self.canonical:
                self.canonical = href

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title" and self._inside_title:
            self.document_title = " ".join(self._title_parts).strip()
            self._inside_title = False

    def close(self) -> None:
        super().close()
        if self._inside_title:
            self.document_title = " ".join(self._title_parts).strip()
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)


def _decode_html(body: bytes, headers: dict[str, str]) -> str:
    content_type = " ".join(
        value for key, value in headers.items() if key.lower() == "content-type"
    )
    match = _CHARSET_RE.search(content_type)
    encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except (LookupError, UnicodeError):
        return body.decode("utf-8", errors="replace")


def parse_html_metadata(
    body: bytes,
    *,
    url: str,
    headers: dict[str, str] | None = None,
) -> MetadataResult:
    """Extract short public metadata without retaining the source HTML."""

    parser = _MetadataParser()
    try:
        parser.feed(_decode_html(body, headers or {}))
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML is an optional fallback path
        return MetadataResult(url=url, reason="MALFORMED_HTML")

    title = parser.meta.get("og:title") or parser.document_title
    description = parser.meta.get("og:description") or parser.meta.get("description", "")
    publisher = (
        parser.meta.get("og:site_name")
        or parser.meta.get("publisher")
        or parser.meta.get("application-name", "")
    )
    try:
        canonical = normalize_url(parser.canonical) if parser.canonical else ""
    except ValueError:
        canonical = ""
    published = parse_datetime(
        parser.meta.get("article:published_time")
        or parser.meta.get("datepublished")
        or parser.meta.get("pubdate")
        or parser.meta.get("date")
    )
    modified = parse_datetime(
        parser.meta.get("article:modified_time")
        or parser.meta.get("datemodified")
    )
    result = MetadataResult(
        url=url,
        title=title.strip(),
        description=description.strip(),
        canonical_url=canonical,
        publisher=publisher.strip(),
        published_at=published,
        modified_at=modified,
    )
    return result if result.success else replace(result, reason="NO_METADATA")


class MetadataEnricher:
    """Bounded, best-effort metadata enrichment for high-ranked news only."""

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        cache: ResponseCache | None = None,
        timeout: float = 3.0,
        max_workers: int = 3,
    ) -> None:
        self.transport = transport or UrlLibTransport()
        self.cache = cache
        self.timeout = max(0.5, timeout)
        self.max_workers = max(1, max_workers)

    @staticmethod
    def _eligible(url: str) -> bool:
        try:
            parts = urlsplit(url)
            return parts.scheme.lower() in {"http", "https"} and bool(parts.hostname)
        except ValueError:
            return False

    def _fetch_one(self, url: str) -> MetadataResult:
        cache_key = ResponseCache.key("GET", url, None)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return MetadataResult.from_cache_payload(url, cached)
        if not self._eligible(url):
            return MetadataResult(url=url, reason="INVALID_URL")
        try:
            response = self.transport.request(
                "GET",
                url,
                {
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                    "User-Agent": "InsightDesk/1.0 (+static-briefing)",
                },
                timeout=self.timeout,
            )
        except (OSError, TimeoutError):
            return MetadataResult(url=url, reason="NETWORK_OR_TIMEOUT")
        if response.status < 200 or response.status >= 300:
            return MetadataResult(url=url, reason=f"HTTP_{response.status}")
        return parse_html_metadata(response.body, url=url, headers=response.headers)

    def enrich(
        self,
        items: tuple[NewsItem, ...],
        *,
        limit: int = 5,
    ) -> tuple[tuple[NewsItem, ...], EnrichmentReport]:
        if limit <= 0:
            return items, EnrichmentReport()
        candidates: list[str] = []
        seen: set[str] = set()
        for item in items:
            url = item.original_url or item.naver_url
            if url and url not in seen and self._eligible(url) and len(candidates) < limit:
                candidates.append(url)
                seen.add(url)
        if not candidates:
            return items, EnrichmentReport()

        results: dict[str, MetadataResult] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(candidates))) as pool:
            futures = {pool.submit(self._fetch_one, url): url for url in candidates}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    results[url] = future.result()
                except Exception:  # noqa: BLE001 - one optional URL cannot fail the briefing
                    results[url] = MetadataResult(url=url, reason="ENRICHMENT_ERROR")

        # Write only after workers finish so a JSON cache cannot be written concurrently.
        if self.cache:
            for url, result in results.items():
                if result.success:
                    try:
                        self.cache.set(ResponseCache.key("GET", url, None), result.to_cache_payload())
                    except OSError:
                        # Cache persistence is an optimization; it must never affect publication.
                        pass

        enriched: list[NewsItem] = []
        for item in items:
            url = item.original_url or item.naver_url
            metadata_result = results.get(url)
            if metadata_result is None or not metadata_result.success:
                enriched.append(item)
                continue
            provenance = tuple(dict.fromkeys((*item.provenance, EvidenceType.ENRICHED_METADATA)))
            enriched.append(
                replace(
                    item,
                    metadata_title=metadata_result.title,
                    metadata_description=metadata_result.description,
                    metadata_canonical_url=metadata_result.canonical_url,
                    publisher=metadata_result.publisher,
                    metadata_published_at=metadata_result.published_at,
                    metadata_modified_at=metadata_result.modified_at,
                    provenance=provenance,
                )
            )
        reasons = tuple(
            sorted({result.reason for result in results.values() if not result.success and result.reason})
        )
        succeeded = sum(1 for result in results.values() if result.success)
        return tuple(enriched), EnrichmentReport(
            attempted=len(candidates),
            succeeded=succeeded,
            failed=len(candidates) - succeeded,
            reasons=reasons,
        )
