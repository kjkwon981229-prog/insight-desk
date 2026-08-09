from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from ..domain.models import NewsItem, Topic
from .clustering import StoryCluster


def _age_hours(item: NewsItem, now: datetime) -> float:
    if not item.published_at:
        return 72.0
    try:
        published = datetime.fromisoformat(item.published_at)
    except ValueError:
        return 72.0
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 3600)


def score_news(items: tuple[NewsItem, ...], topics: tuple[Topic, ...], *, now: datetime) -> tuple[NewsItem, ...]:
    topic_by_id = {topic.id: topic for topic in topics}
    scored: list[NewsItem] = []
    for item in items:
        topic = topic_by_id[item.topic_id]
        text = f"{item.title} {item.summary}".casefold()
        query_match = 1 if item.query.casefold() in text else 0
        recency = max(0.0, 40.0 - min(40.0, _age_hours(item, now) * 1.2))
        score = recency + query_match * 18.0 + min(15.0, len(item.summary) / 80.0) + topic.priority / 20.0
        scored.append(replace(item, score=round(score, 4)))
    return tuple(sorted(scored, key=lambda item: (-item.score, item.title)))


def score_clusters(clusters: tuple[StoryCluster, ...]) -> tuple[StoryCluster, ...]:
    return tuple(
        sorted(
            clusters,
            key=lambda cluster: (
                -(cluster.representative.score + min(10.0, cluster.source_count * 2.0)),
                cluster.representative.title,
            ),
        )
    )
