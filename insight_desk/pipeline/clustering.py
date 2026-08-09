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
    clusters: list[list[NewsItem]] = []
    for item in items:
        placed = False
        for cluster in clusters:
            if cluster[0].topic_id == item.topic_id and any(_similar(item, member) for member in cluster):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    return tuple(StoryCluster(topic_id=cluster[0].topic_id, items=tuple(cluster)) for cluster in clusters)
