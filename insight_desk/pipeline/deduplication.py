from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from difflib import SequenceMatcher

from ..domain.models import NewsItem


def _topic_ids(item: NewsItem) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.matched_topic_ids or (item.topic_id,)))


def _merge_items(existing: NewsItem, incoming: NewsItem) -> NewsItem:
    """Merge duplicate evidence without assigning ownership by config order."""

    base = incoming if len(incoming.summary) > len(existing.summary) else existing
    provenance = tuple(dict.fromkeys((*existing.provenance, *incoming.provenance)))
    topic_ids = tuple(dict.fromkeys((*_topic_ids(existing), *_topic_ids(incoming))))
    retrieval_channels = tuple(
        dict.fromkeys((*existing.retrieval_channels, *incoming.retrieval_channels))
    )
    retrieval_queries = tuple(
        dict.fromkeys(
            (
                *existing.retrieval_queries,
                *incoming.retrieval_queries,
                existing.query,
                incoming.query,
            )
        )
    )
    metadata_source = incoming if "ENRICHED_METADATA" in {getattr(v, "value", v) for v in incoming.provenance} else existing
    return replace(
        base,
        score=max(existing.score, incoming.score),
        metadata_title=metadata_source.metadata_title or base.metadata_title,
        metadata_description=metadata_source.metadata_description or base.metadata_description,
        metadata_canonical_url=metadata_source.metadata_canonical_url or base.metadata_canonical_url,
        publisher=metadata_source.publisher or base.publisher,
        metadata_published_at=metadata_source.metadata_published_at or base.metadata_published_at,
        metadata_modified_at=metadata_source.metadata_modified_at or base.metadata_modified_at,
        provenance=provenance,
        matched_topic_ids=topic_ids,
        retrieval_channels=retrieval_channels,
        retrieval_queries=retrieval_queries,
    )


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
                similarity = SequenceMatcher(None, existing.title, item.title).ratio()
                # Exact URL/hash/title checks above handle the common case.
                # A very high title match is the safe cross-topic fallback.
                if similarity >= 0.97:
                    duplicate_index = index
                    break
        if duplicate_index is not None:
            existing = kept[duplicate_index]
            kept[duplicate_index] = _merge_items(existing, item)
            continue
        index = len(kept)
        kept.append(item)
        if item.canonical_url:
            by_url[item.canonical_url] = index
        by_hash[item.content_hash] = index
        by_title[item.title] = index
    return tuple(kept)
