from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.models import NewsItem


@dataclass(frozen=True)
class StoryCluster:
    topic_id: str
    items: tuple[NewsItem, ...]

    @property
    def representative(self) -> NewsItem:
        return max(self.items, key=lambda item: (item.score, len(item.summary), item.title))

    @property
    def source_count(self) -> int:
        return len({item.source_domain for item in self.items})


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9가-힣]{2,}", text)}


def _similar(a: NewsItem, b: NewsItem) -> bool:
    left = _tokens(a.title)
    right = _tokens(b.title)
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= 0.45


def cluster_news(items: tuple[NewsItem, ...]) -> tuple[StoryCluster, ...]:
    # A duplicate can legitimately match more than one personal interest.
    # Build topic-local views after cross-topic dedupe so config order does not
    # steal attribution from the secondary interest.
    clusters: list[tuple[str, list[NewsItem]]] = []
    for item in items:
        topic_ids = tuple(dict.fromkeys(item.matched_topic_ids or (item.topic_id,)))
        for topic_id in topic_ids:
            placed = False
            for existing_topic_id, cluster in clusters:
                if existing_topic_id == topic_id and any(_similar(item, member) for member in cluster):
                    cluster.append(item)
                    placed = True
                    break
            if not placed:
                clusters.append((topic_id, [item]))
    return tuple(StoryCluster(topic_id=topic_id, items=tuple(cluster)) for topic_id, cluster in clusters)
