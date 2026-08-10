from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from ..domain.models import NewsItem

SEOUL = ZoneInfo("Asia/Seoul")
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def normalize_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    netloc = host
    if parts.username or parts.password:
        netloc = parts.netloc.lower()
    elif port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    query = urlencode(
        sorted((key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if key.lower() not in _TRACKING_PARAMS and not key.lower().startswith("utm_")
        )
    )
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", query, ""))


def parse_datetime(value: object) -> str | None:
    raw = normalize_text(value)
    if not raw:
        return None
    parsed: datetime
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(SEOUL).isoformat(timespec="seconds")


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "미상 출처").lower()


def normalize_news_item(
    raw: dict[str, object],
    *,
    topic_id: str,
    query: str,
    evidence_id: str,
    retrieval_channels: tuple[str, ...] = (),
) -> NewsItem:
    title = normalize_text(raw.get("title"))
    summary = normalize_text(raw.get("description"))
    original_url = normalize_url(raw.get("originallink"))
    naver_url = normalize_url(raw.get("link"))
    canonical_url = original_url or naver_url
    published_at = parse_datetime(raw.get("pubDate"))
    digest = hashlib.sha256(f"{title}\n{summary}".encode("utf-8")).hexdigest()
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query=query,
        title=title or "제목 없음",
        summary=summary,
        original_url=original_url,
        naver_url=naver_url,
        canonical_url=canonical_url,
        published_at=published_at,
        source_domain=_domain(canonical_url),
        content_hash=digest,
        matched_topic_ids=(topic_id,),
        retrieval_channels=tuple(dict.fromkeys(retrieval_channels)),
        retrieval_queries=(query,),
    )


def normalize_news_payloads(
    raw_items: tuple[tuple[object, ...], ...]
) -> tuple[NewsItem, ...]:
    output: list[NewsItem] = []
    counter = 1
    for raw_entry in raw_items:
        if len(raw_entry) == 3:
            topic_id, query, payload = raw_entry
            channels: tuple[str, ...] = ()
        elif len(raw_entry) == 4:
            topic_id, query, channel, payload = raw_entry
            channels = (str(channel),)
        else:
            continue
        if not isinstance(topic_id, str) or not isinstance(query, str) or not isinstance(payload, dict):
            continue
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                output.append(
                    normalize_news_item(
                        item,
                        topic_id=topic_id,
                        query=query,
                        evidence_id=f"N{counter:03d}",
                        retrieval_channels=channels,
                    )
                )
                counter += 1
    return tuple(output)
