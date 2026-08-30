from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from insight_desk.core import FailureKind

from .models import AcquisitionError, ExtractedArticle, FetchedPage


class _PageTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_title = False
        self._title_chunks: list[str] = []
        self.og_title: str | None = None
        self.twitter_title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = {str(key).lower(): value for key, value in attrs}
        if lowered == "title":
            self._inside_title = True
        if lowered == "meta":
            key = str(attributes.get("property") or attributes.get("name") or "").lower()
            content = str(attributes.get("content") or "").strip()
            if key == "og:title" and content:
                self.og_title = content
            elif key == "twitter:title" and content:
                self.twitter_title = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_chunks.append(data)

    def best_title(self) -> str | None:
        for value in (self.og_title, self.twitter_title, "".join(self._title_chunks).strip()):
            if value:
                return value.strip()
        return None


def extract_page_title(html: str) -> str | None:
    parser = _PageTitleParser()
    try:
        parser.feed(html)
    except Exception:
        return None
    return parser.best_title()


class _ArticleMainParser(HTMLParser):
    """Conservative stdlib fallback that reads text only from article/main containers."""

    _TARGET_TAGS = {"article", "main"}
    _SKIP_TAGS = {"script", "style", "nav", "aside", "form", "noscript", "svg"}
    _BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "section", "div", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._target_depth = 0
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lowered = tag.lower()
        if lowered in self._TARGET_TAGS:
            self._target_depth += 1
        if self._target_depth > 0 and lowered in self._SKIP_TAGS:
            self._skip_depth += 1
        if self._target_depth > 0 and self._skip_depth == 0 and lowered in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._target_depth > 0 and self._skip_depth == 0 and lowered in self._BLOCK_TAGS:
            self._chunks.append("\n")
        if self._target_depth > 0 and lowered in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if lowered in self._TARGET_TAGS and self._target_depth > 0:
            self._target_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._target_depth > 0 and self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)
                self._chunks.append(" ")

    def text(self) -> str:
        lines: list[str] = []
        for line in "".join(self._chunks).splitlines():
            normalized = " ".join(line.split())
            if normalized:
                lines.append(normalized)
        return "\n".join(lines)


class UrlLibHtmlFetcher:
    method_id = "http"

    def __init__(self, *, timeout: float = 20.0, max_bytes: int = 6_000_000) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        if max_bytes < 1:
            raise ValueError("max_bytes must be >= 1")
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> FetchedPage:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "User-Agent": "InsightDesk/1.0 (+evidence-preserving acquisition)",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200))
                content_type = str(response.headers.get("Content-Type") or "")
                body = response.read(self.max_bytes + 1)
        except urllib.error.HTTPError as exc:
            kind = FailureKind.TRANSIENT_PROVIDER if exc.code in {429, 500, 502, 503, 504} else FailureKind.INVALID_OUTPUT
            raise AcquisitionError(kind, f"article fetch HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AcquisitionError(FailureKind.TRANSIENT_PROVIDER, f"article fetch failed: {type(exc).__name__}") from exc

        if status < 200 or status >= 300:
            raise AcquisitionError(FailureKind.INVALID_OUTPUT, f"article fetch HTTP {status}")
        if len(body) > self.max_bytes:
            raise AcquisitionError(FailureKind.INVALID_OUTPUT, "article HTML exceeds max_bytes")
        lowered_type = content_type.lower()
        if lowered_type and "html" not in lowered_type and "xhtml" not in lowered_type:
            raise AcquisitionError(FailureKind.INVALID_OUTPUT, f"article response is not HTML: {content_type}")

        charset = "utf-8"
        if "charset=" in lowered_type:
            charset = lowered_type.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        try:
            decoded = body.decode(charset, errors="strict")
        except (LookupError, UnicodeDecodeError):
            decoded = body.decode("utf-8", errors="replace")
        return FetchedPage(
            url=url,
            html=decoded,
            fetched_at=datetime.now(timezone.utc),
            content_type=content_type or None,
        )


class TrafilaturaExtractor:
    method_id = "trafilatura"

    def extract(self, html: str, *, url: str) -> ExtractedArticle:
        try:
            import trafilatura  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AcquisitionError(FailureKind.INVALID_OUTPUT, "trafilatura dependency unavailable") from exc

        try:
            # `favor_precision=True` discards text inside styled inline spans on measured publisher
            # pages, including dates, tenors, percentages, and punctuation required for exact proof.
            body: Any = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="txt",
            )
        except Exception as exc:
            raise AcquisitionError(FailureKind.EXTRACTION_EMPTY, f"trafilatura failed: {type(exc).__name__}") from exc
        return ExtractedArticle(
            body=body if isinstance(body, str) else "",
            page_title=extract_page_title(html),
        )


class ArticleMainTextExtractor:
    """Independent deterministic fallback for explicit HTML article/main content."""

    method_id = "html-article-main"

    def extract(self, html: str, *, url: str) -> ExtractedArticle:
        del url
        parser = _ArticleMainParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            raise AcquisitionError(
                FailureKind.EXTRACTION_EMPTY,
                f"article/main HTML parse failed: {type(exc).__name__}",
            ) from exc
        return ExtractedArticle(
            body=parser.text(),
            page_title=extract_page_title(html),
        )


class PlaywrightHtmlRenderer:
    method_id = "playwright"

    def __init__(self, *, timeout_ms: int = 20_000) -> None:
        if timeout_ms < 1:
            raise ValueError("timeout_ms must be >= 1")
        self.timeout_ms = timeout_ms

    def render(self, url: str) -> FetchedPage:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AcquisitionError(FailureKind.INVALID_OUTPUT, "playwright dependency unavailable") from exc

        try:
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    rendered = page.content()
                finally:
                    browser.close()
        except Exception as exc:
            raise AcquisitionError(FailureKind.EXTRACTION_EMPTY, f"playwright render failed: {type(exc).__name__}") from exc
        return FetchedPage(
            url=url,
            html=rendered,
            fetched_at=datetime.now(timezone.utc),
            content_type="text/html; rendered=playwright",
        )
