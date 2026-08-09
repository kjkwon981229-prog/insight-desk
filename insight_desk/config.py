from __future__ import annotations

import json
from pathlib import Path

from .domain.models import KeywordGroup, Topic


class ConfigError(ValueError):
    pass


def load_topics(path: Path) -> tuple[Topic, tuple[KeywordGroup, ...]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"topic configuration cannot be read: {path.name}") from exc

    topics: list[Topic] = []
    groups: list[KeywordGroup] = []
    for topic_raw in raw.get("topics", []):
        topic_id = str(topic_raw["id"])
        topics.append(
            Topic(
                id=topic_id,
                name=str(topic_raw["name"]),
                enabled=bool(topic_raw.get("enabled", True)),
                conditional=bool(topic_raw.get("conditional", False)),
                priority=int(topic_raw.get("priority", 50)),
                news_queries=tuple(str(x) for x in topic_raw.get("news_queries", [])),
                query_families=tuple(
                    tuple(str(query) for query in family if str(query).strip())
                    for family in topic_raw.get("query_families", [])
                    if isinstance(family, list)
                ),
                candidate_budget=max(10, int(topic_raw.get("candidate_budget", 40))),
                selection_cap=max(1, int(topic_raw.get("selection_cap", 3))),
                intent_anchors=tuple(
                    str(value) for value in topic_raw.get("intent_anchors", []) if str(value).strip()
                ),
                negative_context=tuple(
                    str(value) for value in topic_raw.get("negative_context", []) if str(value).strip()
                ),
                event_terms=tuple(
                    str(value) for value in topic_raw.get("event_terms", []) if str(value).strip()
                ),
                required_intent_terms=tuple(
                    str(value)
                    for value in topic_raw.get("required_intent_terms", [])
                    if str(value).strip()
                ),
            )
        )
        for index, group_raw in enumerate(topic_raw.get("trend_groups", []), start=1):
            keywords = tuple(str(x) for x in group_raw.get("keywords", []))
            if not keywords or len(keywords) > 20:
                raise ConfigError(f"trend group has invalid keyword count: {topic_id}")
            groups.append(
                KeywordGroup(
                    id=str(group_raw.get("id", f"{topic_id}_{index}")),
                    topic_id=topic_id,
                    name=str(group_raw["name"]),
                    keywords=keywords,
                    enabled=bool(group_raw.get("enabled", True)),
                )
            )
    if not topics:
        raise ConfigError("topic configuration is empty")
    return tuple(topics), tuple(groups)
