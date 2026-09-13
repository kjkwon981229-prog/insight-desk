from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, cast

from insight_desk.core import FailureKind

from .models import AcquisitionError, ExtractedArticle, FetchedPage


class _PageTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_title = False
        self._title_chunks: list[str] = []
        self.og_title: str | None = None
        self.twitter_title: str | None = None
        self.site_names: set[str] = set()
        self.article_published_times: list[str] = []
        self.date_published_values: list[str] = []
        self._inside_json_ld = False
        self._json_ld_chunks: list[str] = []
        self.json_ld_payloads: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = {str(key).lower(): value for key, value in attrs}
        if lowered == "title":
            self._inside_title = True
        if lowered == "script":
            script_type = str(attributes.get("type") or "").split(";", 1)[0].strip().lower()
            if script_type == "application/ld+json":
                self._inside_json_ld = True
                self._json_ld_chunks = []
        if lowered == "meta":
            key = str(attributes.get("property") or attributes.get("name") or "").lower()
            content = str(attributes.get("content") or "").strip()
            if key == "og:title" and content:
                self.og_title = content
            elif key == "twitter:title" and content:
                self.twitter_title = content
            elif key == "og:site_name" and content:
                self.site_names.add(content)
            elif key == "article:published_time" and content:
                self.article_published_times.append(content)
            elif key in {"datepublished", "date_published"} and content:
                self.date_published_values.append(content)
        if lowered == "time":
            itemprop = str(attributes.get("itemprop") or "").strip().lower()
            value = str(attributes.get("datetime") or "").strip()
            if itemprop == "datepublished" and value:
                self.date_published_values.append(value)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._inside_title = False
        if lowered == "script" and self._inside_json_ld:
            self.json_ld_payloads.append("".join(self._json_ld_chunks))
            self._json_ld_chunks = []
            self._inside_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_chunks.append(data)
        if self._inside_json_ld:
            self._json_ld_chunks.append(data)

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


def _parse_aware_publication_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(candidate)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _json_ld_article_publication_times(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, list):
        for child in value:
            values.extend(_json_ld_article_publication_times(child))
        return tuple(values)
    if not isinstance(value, dict):
        return ()

    raw_types = value.get("@type")
    types = (raw_types,) if isinstance(raw_types, str) else raw_types
    if isinstance(types, (tuple, list)) and any(
        isinstance(item, str) and item.casefold() in {
            "article",
            "newsarticle",
            "reportagenewsarticle",
        }
        for item in types
    ):
        published = value.get("datePublished")
        if isinstance(published, str) and published.strip():
            values.append(published)
    for child in value.values():
        if isinstance(child, (dict, list)):
            values.extend(_json_ld_article_publication_times(child))
    return tuple(values)


def extract_page_published_at(html: str) -> datetime | None:
    """Return an explicit publisher-page publication time when it is unambiguous and aware."""

    parser = _PageTitleParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return None

    for value in (*parser.article_published_times, *parser.date_published_values):
        parsed = _parse_aware_publication_time(value)
        if parsed is not None:
            return parsed
    for payload in parser.json_ld_payloads:
        try:
            decoded = json.loads(payload)
        except (TypeError, ValueError):
            continue
        for value in _json_ld_article_publication_times(decoded):
            parsed = _parse_aware_publication_time(value)
            if parsed is not None:
                return parsed
    return None


def strip_document_publisher_prefix(body: str, html: str) -> str:
    """Remove a detached label only when the document identifies that exact publisher.

    Bracketed qualifications remain evidence. No publisher-name vocabulary or
    inferred mapping from hostnames participates in this boundary decision.
    """
    parser = _PageTitleParser()
    try:
        parser.feed(html)
    except Exception:
        return body
    if len(parser.site_names) != 1:
        return body
    publisher = next(iter(parser.site_names))
    label = f"[{publisher}]"
    if body.startswith(label) and body[len(label):len(label) + 1].isspace():
        return body[len(label):].lstrip()
    return body


def _preserve_article_root_text_boundaries(html: str) -> str:
    """Make source-visible article block boundaries explicit before text extraction.

    Some publishers place a multi-line deck in an inline element directly under ``article`` or
    ``main`` and put the lead paragraph in that element's tail text. Text extractors can otherwise
    concatenate the deck's final line and the lead into one invented proposition. A direct child
    that already contains a forced line break is structurally multi-line, so insert one HTML break
    before any non-empty tail. No source text is edited or reordered.
    """

    try:
        from lxml import etree, html as lxml_html  # type: ignore[import-untyped]
    except ImportError:
        return html

    try:
        document = lxml_html.fromstring(html)
    except (ValueError, etree.ParserError):
        return html

    changed = False
    roots = document.xpath("descendant-or-self::article | descendant-or-self::main")
    for root in roots:
        for child in tuple(root):
            tail = child.tail
            if not tail or not tail.strip():
                continue
            has_forced_line_break = any(
                isinstance(descendant.tag, str) and descendant.tag.casefold() == "br"
                for descendant in child.iterdescendants()
            )
            if not has_forced_line_break:
                continue
            child.tail = None
            boundary = etree.Element("br")
            boundary.tail = tail
            child.addnext(boundary)
            changed = True

    if not changed:
        return html
    return cast(str, etree.tostring(document, encoding="unicode", method="html"))


_PROSE_BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "blockquote"})


def _tag_name(node: Any) -> str:
    return node.tag.casefold() if isinstance(getattr(node, "tag", None), str) else ""


def _direct_table_rows(table: Any) -> tuple[Any, ...]:
    rows: list[Any] = []
    for child in table:
        tag = _tag_name(child)
        if tag == "tr":
            rows.append(child)
        elif tag in {"thead", "tbody", "tfoot"}:
            rows.extend(grandchild for grandchild in child if _tag_name(grandchild) == "tr")
    return tuple(rows)


def _nearest_table(node: Any) -> Any | None:
    for ancestor in node.iterancestors():
        if _tag_name(ancestor) == "table":
            return ancestor
    return None


def _is_single_row_prose_layout_table(table: Any) -> bool:
    """Identify a layout table without class names, publishers, or article wording.

    A real data table distributes values across cells and/or rows. The measured failure instead
    has one row where exactly one cell owns several long-form paragraph blocks while its sibling
    cells are layout/navigation. Rendering that wrapper as a table erases the paragraph boundaries.
    """

    rows = _direct_table_rows(table)
    if len(rows) != 1:
        return False
    cells = tuple(child for child in rows[0] if _tag_name(child) in {"td", "th"})
    if len(cells) < 2:
        return False

    prose_cells = 0
    for cell in cells:
        block_texts: list[str] = []
        for descendant in cell.iterdescendants():
            if _tag_name(descendant) not in _PROSE_BLOCK_TAGS:
                continue
            if _nearest_table(descendant) is not table:
                continue
            normalized = " ".join("".join(descendant.itertext()).replace("\xa0", " ").split())
            if normalized:
                block_texts.append(normalized)
        if len(block_texts) >= 3 and sum(map(len, block_texts)) >= 240:
            prose_cells += 1
    return prose_cells == 1


def _has_single_row_prose_layout_table(html: str) -> bool:
    try:
        from lxml import etree, html as lxml_html  # type: ignore[import-untyped]
    except ImportError:
        return False
    try:
        document = lxml_html.fromstring(html)
    except (ValueError, etree.ParserError):
        return False
    return any(_is_single_row_prose_layout_table(table) for table in document.iter("table"))


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
            prepared_html = _preserve_article_root_text_boundaries(html)
            # A single-row multi-cell layout wrapper can make trafilatura serialize an entire
            # article as one ``| ... |`` table row, destroying source paragraph boundaries. Only
            # suppress table rendering when the DOM proves that structural layout pattern; real
            # multi-row data tables retain the normal extraction route.
            body: Any = trafilatura.extract(
                prepared_html,
                include_comments=False,
                include_tables=not _has_single_row_prose_layout_table(prepared_html),
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
            parser.feed(_preserve_article_root_text_boundaries(html))
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
