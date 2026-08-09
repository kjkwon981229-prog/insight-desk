from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher

from ..domain.models import NewsItem


def _published(item: NewsItem) -> datetime:
    if not item.published_at:
        return datetime.min
    try:
        return datetime.fromisoformat(item.published_at)
    except ValueError:
        return datetime.min


def deduplicate_news(items: tuple[NewsItem, ...]) -> tuple[NewsItem, ...]:
    kept: list[NewsItem] = []
    by_url: dict[str, int] = {}
    by_hash: dict[str, int] = {}
    by_title: dict[str, int] = {}
    for item in sorted(items, key=_published, reverse=True):
        duplicate_index: int | None = None
        if item.canonical_url and item.canonical_url in by_url:
            duplicate_index = by_url[item.canonical_url]
        elif item.content_hash in by_hash:
            duplicate_index = by_hash[item.content_hash]
        elif item.title in by_title:
            duplicate_index = by_title[item.title]
        else:
            for index, existing in enumerate(kept):
                if existing.topic_id != item.topic_id:
                    continue
                similarity = SequenceMatcher(None, existing.title, item.title).ratio()
                if similarity >= 0.94:
                    duplicate_index = index
                    break
        if duplicate_index is not None:
            existing = kept[duplicate_index]
            if len(item.summary) > len(existing.summary):
                kept[duplicate_index] = item
            continue
        index = len(kept)
        kept.append(item)
        if item.canonical_url:
            by_url[item.canonical_url] = index
        by_hash[item.content_hash] = index
        by_title[item.title] = index
    return tuple(kept)
