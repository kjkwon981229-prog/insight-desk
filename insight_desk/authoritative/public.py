from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ..collectors.transport import HttpResponse, Transport, UrlLibTransport
from ..domain.models import AuthorityEvidence, AuthoritySourceType, NewsItem
from ..pipeline.semantics import compact, fold
from .adapters import AdapterPayload, AdapterResult
from .config import PublicSourceConfig


_TRUNCATION_RE = re.compile(r"\.{2,}|…|·{2,}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")
_NUMBER_RE = re.compile(r"(?<!\d)\d[\d,.]*(?:\s?(?:%|명|건|개|점|위|원|억원|조원|대))?")
_DATE_RE = re.compile(
    r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|월|일)"
    r"|20\d{2}[./-]\d{1,2}(?:[./-]\d{1,2})?"
)
_STOPWORDS = frozenset(
    {
        "관련", "보도", "소식", "기사", "발표", "공개", "확인", "공식", "올해", "이번",
        "오늘", "일정", "전체", "자료", "페이지", "시스템", "홈페이지", "전했다",
    }
)


@dataclass(frozen=True)
class _Link:
    text: str
    href: str


@dataclass(frozen=True)
class _Page:
    title: str
    description: str
    text: str
    links: tuple[_Link, ...]


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.description = ""
        self.text_parts: list[str] = []
        self.links: list[_Link] = []
        self._in_title = False
        self._skip_depth = 0
        self._link_href: str | None = None
        self._link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "template"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._in_title = True
        elif lowered == "meta" and attrs_map.get("name", "").casefold() == "description":
            self.description = attrs_map.get("content", "").strip()
        elif lowered == "a":
            self._link_href = attrs_map.get("href", "").strip() or None
            self._link_parts = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "template"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if lowered == "title":
            self._in_title = False
        elif lowered == "a" and self._link_href:
            text = " ".join(self._link_parts).strip()
            if text:
                self.links.append(_Link(text=text, href=self._link_href))
            self._link_href = None
            self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)
        if self._link_href:
            self._link_parts.append(text)


def _parse_page(body: bytes) -> _Page:
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - bytes.decode is defensive
        raise ValueError("INVALID_HTML") from exc
    parser = _PageParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise ValueError("INVALID_HTML") from exc
    title = " ".join(parser.title_parts).strip()
    visible = " ".join(parser.text_parts).strip()
    if not title and not visible:
        raise ValueError("EMPTY_HTML")
    return _Page(title=title[:240], description=parser.description[:500], text=visible[:120_000], links=tuple(parser.links[:500]))


def _host_allowed(url: str, domains: tuple[str, ...]) -> bool:
    host = (urlsplit(url).hostname or "").removeprefix("www.").rstrip(".").casefold()
    return bool(host) and any(
        host == domain.removeprefix("www.").rstrip(".").casefold()
        or host.endswith(f".{domain.removeprefix('www.').rstrip('.').casefold()}")
        for domain in domains
    )


def _candidate_text(item: NewsItem) -> str:
    values = (item.metadata_title, item.title, item.metadata_description)
    return " ".join(value for value in values if value and not _TRUNCATION_RE.search(value))


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(value)
        if token.casefold() not in _STOPWORDS and compact(token) not in _STOPWORDS
    }


def _facts(value: str) -> set[str]:
    found = {re.sub(r"\s+", "", match) for match in _DATE_RE.findall(value)}
    found.update(re.sub(r"\s+", "", match) for match in _NUMBER_RE.findall(value))
    return {fact for fact in found if fact}


def _fact_keys(value: str) -> set[str]:
    """Normalize month/day and numeric facts enough for page matching."""

    keys: set[str] = set()
    for fact in _facts(value):
        digits = re.sub(r"\D", "", fact)
        if digits and not (len(digits) == 4 and digits.startswith("20")):
            keys.add(digits.lstrip("0") or "0")
        month_day = re.search(r"(\d{1,2})월(?:\s?(\d{1,2})일)?", fact)
        if month_day:
            keys.add(f"m{int(month_day.group(1)):02d}")
            if month_day.group(2):
                keys.add(f"d{int(month_day.group(2)):02d}")
    return keys


def _same_event_match(item: NewsItem, source: PublicSourceConfig, page: _Page) -> tuple[bool, str, tuple[str, ...], str]:
    title = str(item.metadata_title or item.title or "").strip()
    if not title or _TRUNCATION_RE.search(title):
        return False, "", (), ""
    article = _candidate_text(item)
    page_text = f"{page.title} {page.description} {page.text}"
    article_folded = fold(article)
    page_folded = fold(page_text)
    entity_matches = [alias for alias in source.entity_aliases if compact(alias) in compact(article_folded) and compact(alias) in compact(page_folded)]
    marker_matches = [marker for marker in source.event_markers if compact(marker) in compact(article_folded) and compact(marker) in compact(page_folded)]
    if not entity_matches or not marker_matches:
        return False, "", (), ""
    article_facts = _fact_keys(article)
    page_facts = _fact_keys(page_text)
    shared_facts = tuple(sorted(article_facts.intersection(page_facts)))
    article_tokens = _tokens(title)
    page_tokens = _tokens(page_text)
    shared_tokens = article_tokens.intersection(page_tokens)
    link_text = ""
    link_url = ""
    for link in page.links:
        link_folded = fold(link.text)
        if any(compact(alias) in compact(link_folded) for alias in entity_matches) and any(
            compact(marker) in compact(link_folded) for marker in marker_matches
        ):
            link_text = link.text.strip()
            link_url = link.href
            break
    # A broad official listing can mention the same entity and action many
    # times.  Require an event-specific anchor and either an explicit
    # date/number match or several concrete title tokens in that anchor.
    link_tokens = _tokens(link_text)
    if not link_text or (not shared_facts and len(article_tokens.intersection(link_tokens)) < 3):
        return False, "", (), ""
    return True, link_text or page.title or source.publisher, shared_facts[:6], link_url


class PublicOfficialAdapter:
    """Bounded, event-driven adapter for a configured public official page."""

    def __init__(self, *, config: PublicSourceConfig, transport: Transport | None = None, timeout: float = 5.0) -> None:
        self.config = config
        self.transport = transport or UrlLibTransport()
        self.timeout = max(1.0, min(10.0, timeout))

    def fetch(self, items: tuple[NewsItem, ...]) -> AdapterPayload:
        if not _host_allowed(self.config.url, self.config.trusted_domains):
            return AdapterPayload(AdapterResult(self.config.id, failure_reason="UNTRUSTED_CONFIGURED_DOMAIN"))
        candidates = tuple(
            item
            for item in items
            if item.topic_id in self.config.topic_ids
            and any(compact(marker) in compact(str(item.metadata_title or item.title)) for marker in self.config.event_markers)
        )
        if not candidates:
            return AdapterPayload(AdapterResult(self.config.id, failure_reason="NO_CANDIDATE_MATCH"))
        attempted = 0
        try:
            attempted = 1
            response = self.transport.request(
                "GET",
                self.config.url,
                {"Accept": "text/html,application/xhtml+xml", "User-Agent": "InsightDesk/1.0"},
                timeout=self.timeout,
            )
            if response.status < 200 or response.status >= 300:
                return AdapterPayload(AdapterResult(self.config.id, attempted=attempted, failure_reason=f"HTTP_{response.status}"))
            page = _parse_page(response.body)
        except (OSError, TimeoutError):
            return AdapterPayload(AdapterResult(self.config.id, attempted=attempted, failure_reason="NETWORK_OR_TIMEOUT"))
        except ValueError as exc:
            return AdapterPayload(AdapterResult(self.config.id, attempted=attempted, failure_reason=str(exc)))

        evidence: list[tuple[str, AuthorityEvidence]] = []
        for item in candidates:
            matched, matched_text, fact_values, link_href = _same_event_match(item, self.config, page)
            if not matched:
                continue
            candidate_url = urljoin(self.config.url, link_href) if link_href else self.config.url
            if not _host_allowed(candidate_url, self.config.trusted_domains):
                candidate_url = self.config.url
            event_key = hashlib.sha256(
                f"{self.config.id}|{compact(item.title)}".encode("utf-8")
            ).hexdigest()[:20]
            evidence.append(
                (
                    item.evidence_id,
                    AuthorityEvidence(
                        adapter=self.config.id,
                        source_type=AuthoritySourceType(self.config.source_type),
                        authority_strength="HIGH",
                        title=matched_text,
                        description=matched_text,
                        canonical_url=candidate_url,
                        publisher=self.config.publisher,
                        event_key=f"PUBLIC:{self.config.id}:{event_key}",
                        fact_values=fact_values,
                    ),
                )
            )
        result = AdapterResult(
            self.config.id,
            attempted=attempted,
            success=True,
            candidates_matched=len({item_id for item_id, _ in evidence}),
            events_augmented=len(evidence),
            official_facts_added=sum(len(facts.fact_values) for _, facts in evidence),
            stories_affected=len({item_id for item_id, _ in evidence}),
        )
        return AdapterPayload(result, tuple(evidence))
