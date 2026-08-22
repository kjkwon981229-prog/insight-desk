from __future__ import annotations

import hashlib
import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from insight_desk.core import FailureKind, RawArticle

_TAG_RE = re.compile(r"<[^>]+>")


class AcquisitionError(RuntimeError):
    def __init__(self, failure_kind: FailureKind, detail: str) -> None:
        self.failure_kind = failure_kind
        self.detail = detail
        super().__init__(detail)


def _require_text(name: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{name} must be non-empty")
    return stripped


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _clean_search_markup(value: str) -> str:
    return html_lib.unescape(_TAG_RE.sub("", value)).strip()


def _candidate_id(url: str) -> str:
    return "article-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True, slots=True)
class ArticleCandidate:
    candidate_id: str
    url: str
    search_title: str
    source_name: str
    published_at: datetime | None
    topic_ids: tuple[str, ...]
    query: str
    retrieved_via: str = "naver_search"

    def __post_init__(self) -> None:
        _require_text("candidate_id", self.candidate_id)
        _require_text("url", self.url)
        _require_text("search_title", self.search_title)
        _require_text("source_name", self.source_name)
        _require_text("query", self.query)
        _require_text("retrieved_via", self.retrieved_via)
        if self.published_at is not None:
            _require_aware("published_at", self.published_at)
        if not self.topic_ids or any(not item.strip() for item in self.topic_ids):
            raise ValueError("topic_ids must contain non-empty values")
        if len(set(self.topic_ids)) != len(self.topic_ids):
            raise ValueError("topic_ids must be unique")


@dataclass(frozen=True, slots=True)
class FetchedPage:
    url: str
    html: str
    fetched_at: datetime
    content_type: str | None = None

    def __post_init__(self) -> None:
        _require_text("url", self.url)
        if not isinstance(self.html, str):
            raise ValueError("html must be a string")
        _require_aware("fetched_at", self.fetched_at)


@dataclass(frozen=True, slots=True)
class ExtractedArticle:
    body: str
    page_title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.body, str):
            raise ValueError("body must be a string")
        if self.page_title is not None and not self.page_title.strip():
            raise ValueError("page_title must be non-empty when provided")


@dataclass(frozen=True, slots=True)
class ExtractionQuality:
    acceptable: bool
    character_count: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractionQualityPolicy:
    min_non_whitespace_chars: int = 240
    max_duplicate_line_ratio: float = 0.60

    def __post_init__(self) -> None:
        if self.min_non_whitespace_chars < 1:
            raise ValueError("min_non_whitespace_chars must be >= 1")
        if not 0 <= self.max_duplicate_line_ratio <= 1:
            raise ValueError("max_duplicate_line_ratio must be between 0 and 1")

    def assess(self, text: str) -> ExtractionQuality:
        compact_count = sum(not char.isspace() for char in text)
        reasons: list[str] = []
        if compact_count < self.min_non_whitespace_chars:
            reasons.append("too_short")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 6:
            duplicate_count = len(lines) - len(set(lines))
            ratio = duplicate_count / len(lines)
            if ratio > self.max_duplicate_line_ratio:
                reasons.append("repetitive_navigation_like_text")

        return ExtractionQuality(
            acceptable=not reasons,
            character_count=compact_count,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    article: RawArticle
    extraction_method: str
    fallback_used: bool
    quality: ExtractionQuality
    source_html_sha256: str


def normalize_naver_items(
    payload: dict[str, object],
    *,
    topic_id: str,
    query: str,
) -> tuple[ArticleCandidate, ...]:
    """Normalize NAVER search items without treating snippets as article bodies."""

    _require_text("topic_id", topic_id)
    _require_text("query", query)
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raise AcquisitionError(FailureKind.INVALID_OUTPUT, "NAVER items must be a list")

    candidates: list[ArticleCandidate] = []
    seen_urls: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item: dict[str, Any] = raw
        original = str(item.get("originallink") or "").strip()
        fallback = str(item.get("link") or "").strip()
        url = original or fallback
        if not url or url in seen_urls:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue

        title = _clean_search_markup(str(item.get("title") or ""))
        if not title:
            continue
        hostname = (parsed.hostname or parsed.netloc).lower()
        published_at: datetime | None = None
        pub_date = str(item.get("pubDate") or "").strip()
        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date)
                if published_at.tzinfo is None or published_at.utcoffset() is None:
                    published_at = None
            except (TypeError, ValueError, OverflowError):
                published_at = None

        candidates.append(
            ArticleCandidate(
                candidate_id=_candidate_id(url),
                url=url,
                search_title=title,
                source_name=hostname,
                published_at=published_at,
                topic_ids=(topic_id,),
                query=query,
            )
        )
        seen_urls.add(url)
    return tuple(candidates)
