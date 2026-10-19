from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

from insight_desk.core import FailureKind

from .discovery import (
    DiscoveryError,
    _aware_pubdate,
    _stable_candidate_id,
    _validated_http_url,
)
from .models import ArticleCandidate

_ATOM = "{http://www.w3.org/2005/Atom}"
_MAX_FEED_BYTES = 2_000_000


def _parse_atom_or_iso(value: str):
    from datetime import datetime, timezone

    value = value.strip()
    if not value:
        return None
    parsed = _aware_pubdate(value)
    if parsed is not None:
        return parsed
    try:
        iso = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if iso.tzinfo is None or iso.utcoffset() is None:
        return iso.replace(tzinfo=timezone.utc)
    return iso


@dataclass(slots=True)
class FeedRssDiscovery:
    """Read a topic's configured public RSS/Atom feeds directly (no search engine in between).

    The feed only supplies candidate URLs, titles and dates; every article still goes through the
    unchanged acquisition, freshness, hard-filter, scoring and verification stages.
    """

    opener: Callable[..., Any] = urllib.request.urlopen
    timeout: float = 15.0
    route_id: str = "feed_rss"
    _stats: dict[str, dict[str, object]] = field(default_factory=dict, init=False, repr=False)

    @property
    def route_stats(self) -> dict[str, dict[str, object]]:
        return {key: dict(value) for key, value in self._stats.items()}

    def fetch(self, feed_url: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        stats = self._stats.setdefault(
            urlparse(feed_url).hostname or feed_url, {"calls": 0, "errors": 0, "candidates": 0}
        )
        stats["calls"] = int(stats["calls"]) + 1
        request = urllib.request.Request(feed_url, headers={"User-Agent": "InsightDesk/1.0 (+personal feed reader)"})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read(_MAX_FEED_BYTES)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            stats["errors"] = int(stats["errors"]) + 1
            raise DiscoveryError(FailureKind.TRANSIENT_PROVIDER, f"feed fetch failed:{type(exc).__name__}") from exc
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            stats["errors"] = int(stats["errors"]) + 1
            raise DiscoveryError(FailureKind.INVALID_OUTPUT, "feed is invalid XML") from exc

        entries: list[tuple[str, str, str]] = []  # (title, link, date text)
        for item in root.findall(".//item"):
            entries.append(
                (
                    (item.findtext("title") or "").strip(),
                    (item.findtext("link") or "").strip(),
                    (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""),
                )
            )
        for entry in root.findall(f".//{_ATOM}entry"):
            link = ""
            for node in entry.findall(f"{_ATOM}link"):
                if node.get("rel", "alternate") == "alternate" and node.get("href"):
                    link = node.get("href", "")
                    break
            entries.append(
                (
                    (entry.findtext(f"{_ATOM}title") or "").strip(),
                    link.strip(),
                    entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated") or "",
                )
            )

        output: list[ArticleCandidate] = []
        seen: set[str] = set()
        for title, link, date_text in entries:
            url = _validated_http_url(link)
            if not title or not url or url in seen:
                continue
            parsed = urlparse(url)
            output.append(
                ArticleCandidate(
                    candidate_id=_stable_candidate_id(self.route_id, url),
                    url=url,
                    search_title=title,
                    source_name=(parsed.hostname or parsed.netloc).lower(),
                    published_at=_parse_atom_or_iso(date_text),
                    topic_ids=(topic_id,),
                    query=f"feed:{parsed.hostname or parsed.netloc}",
                    retrieved_via=self.route_id,
                )
            )
            seen.add(url)
            if len(output) >= limit:
                break
        stats["candidates"] = int(stats["candidates"]) + len(output)
        return tuple(output)
