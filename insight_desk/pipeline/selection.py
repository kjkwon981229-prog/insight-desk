from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import EvidenceType, NewsItem, Topic
from .clustering import StoryCluster


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[StoryCluster, ...]
    audit: tuple[dict[str, object], ...]


def topic_ids_for_item(item: NewsItem) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.matched_topic_ids or (item.topic_id,)))


def candidate_key(cluster: StoryCluster) -> str:
    representative = cluster.representative
    return representative.canonical_url or representative.content_hash or representative.evidence_id


def _publisher_count(cluster: StoryCluster) -> int:
    return len({item.source_domain for item in cluster.items if item.source_domain})


def candidate_quality(cluster: StoryCluster, topic: Topic) -> float:
    """Score a story inside one topic without using raw media volume.

    The existing item score remains a recency/query signal. Priority is removed
    from that score here and used only as a small tie-breaker in final lineup
    selection. Publisher diversity and official evidence add more value than
    repeated syndicated copies.
    """

    representative = cluster.representative
    base = max(0.0, representative.score - topic.priority / 20.0)
    diversity = min(3, _publisher_count(cluster)) * 3.0
    official = 5.0 if any(EvidenceType.OFFICIAL_SOURCE in item.provenance for item in cluster.items) else 0.0
    metadata = 1.0 if any(EvidenceType.ENRICHED_METADATA in item.provenance for item in cluster.items) else 0.0
    completeness = 3.0 if len(representative.title) >= 10 and len(representative.summary) >= 18 else 0.0
    repeated_copy_penalty = min(4.0, max(0, len(cluster.items) - _publisher_count(cluster)) * 0.75)
    return round(base + diversity + official + metadata + completeness - repeated_copy_penalty, 4)


def _meaningful(cluster: StoryCluster, quality: float) -> bool:
    representative = cluster.representative
    return quality >= 20.0 and len(representative.title.strip()) >= 8 and len(representative.summary.strip()) >= 15


def _coverage(cluster: StoryCluster) -> set[str]:
    covered = {cluster.topic_id}
    for item in cluster.items:
        covered.update(topic_ids_for_item(item))
    return covered


def select_clusters(
    clusters: tuple[StoryCluster, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int = 10,
) -> SelectionResult:
    """Select a repeatable, personal, multi-topic lineup.

    Core topics receive a representation opportunity only when a meaningful
    candidate exists. Conditional topics follow the same quality gate. The
    remaining slots use quality plus mild priority tie-breaking with a topic
    saturation penalty; no filler is created to make a quota look balanced.
    """

    topic_by_id = {topic.id: topic for topic in topics}
    enabled_topics = tuple(topic for topic in topics if topic.enabled)
    grouped: dict[str, list[tuple[StoryCluster, float, bool]]] = {topic.id: [] for topic in enabled_topics}
    for cluster in clusters:
        topic = topic_by_id.get(cluster.topic_id)
        if topic is None or not topic.enabled:
            continue
        quality = candidate_quality(cluster, topic)
        grouped.setdefault(cluster.topic_id, []).append((cluster, quality, _meaningful(cluster, quality)))
    for values in grouped.values():
        values.sort(key=lambda value: (-value[1], value[0].representative.title))

    selected: list[StoryCluster] = []
    selected_keys: set[str] = set()
    selected_coverage: set[str] = set()
    topic_counts: dict[str, int] = {topic.id: 0 for topic in enabled_topics}
    records: dict[tuple[str, str], dict[str, object]] = {}

    def record(cluster: StoryCluster, *, quality: float, meaningful: bool, selected_value: bool, reason: str, penalty: float = 0.0) -> None:
        topic = topic_by_id[cluster.topic_id]
        records[(cluster.topic_id, candidate_key(cluster))] = {
            "candidate_key": candidate_key(cluster),
            "topic_id": cluster.topic_id,
            "topic_name": topic.name,
            "quality": quality,
            "topic_local_rank": next(
                (index for index, value in enumerate(grouped.get(cluster.topic_id, ()), 1) if candidate_key(value[0]) == candidate_key(cluster)),
                0,
            ),
            "qualifying": meaningful,
            "selected": selected_value,
            "reason": reason,
            "saturation_penalty": round(penalty, 3),
            "conditional": topic.conditional,
            "source_diversity": _publisher_count(cluster),
        }

    def choose(cluster: StoryCluster, quality: float, reason: str, penalty: float = 0.0) -> None:
        key = candidate_key(cluster)
        if key in selected_keys or len(selected) >= limit:
            return
        selected.append(cluster)
        selected_keys.add(key)
        topic_counts[cluster.topic_id] = topic_counts.get(cluster.topic_id, 0) + 1
        selected_coverage.update(_coverage(cluster))
        record(cluster, quality=quality, meaningful=True, selected_value=True, reason=reason, penalty=penalty)

    qualifying_topic_ids = {
        topic_id for topic_id, values in grouped.items() if any(meaningful for _, _, meaningful in values)
    }

    # Coverage floor: one meaningful candidate per represented interest. A
    # cross-topic duplicate can satisfy both interests without being rendered twice.
    for topic in enabled_topics:
        if topic.id in selected_coverage or len(selected) >= limit:
            continue
        for cluster, quality, meaningful in grouped.get(topic.id, ()):
            if meaningful and candidate_key(cluster) not in selected_keys:
                choose(cluster, quality, "coverage floor")
                break
            record(cluster, quality=quality, meaningful=meaningful, selected_value=False, reason="cross-topic duplicate" if candidate_key(cluster) in selected_keys else "not selected")

    cap = 3 if len(qualifying_topic_ids) >= 4 else limit
    candidates: dict[str, tuple[StoryCluster, float, bool]] = {}
    for topic_id, values in grouped.items():
        for cluster, quality, meaningful in values:
            key = candidate_key(cluster)
            existing = candidates.get(key)
            if existing is None or quality > existing[1]:
                candidates[key] = (cluster, quality, meaningful)

    while len(selected) < limit:
        available: list[tuple[float, StoryCluster, float, float]] = []
        for key, (cluster, quality, meaningful) in candidates.items():
            if key in selected_keys or not meaningful:
                continue
            current_count = topic_counts.get(cluster.topic_id, 0)
            if current_count >= cap and len(qualifying_topic_ids) >= 2:
                continue
            penalty = min(12.0, current_count * 4.0)
            adjacency = 8.0 if selected and selected[-1].topic_id == cluster.topic_id else 0.0
            if len(selected) >= 2 and selected[-1].topic_id == selected[-2].topic_id == cluster.topic_id:
                adjacency += 12.0
            priority_tie = topic_by_id[cluster.topic_id].priority / 1000.0
            available.append((quality - penalty - adjacency + priority_tie, cluster, penalty, adjacency))
        if not available:
            break
        _, cluster, penalty, _ = max(available, key=lambda value: (value[0], -len(selected), value[1].representative.title))
        choose(cluster, candidate_quality(cluster, topic_by_id[cluster.topic_id]), "quality + diversity", penalty)

    for topic_id, values in grouped.items():
        for cluster, quality, meaningful in values:
            key = (topic_id, candidate_key(cluster))
            if key in records:
                continue
            reason = "quality threshold" if not meaningful else ("topic cap" if topic_counts.get(topic_id, 0) >= cap else "remaining slot")
            record(cluster, quality=quality, meaningful=meaningful, selected_value=False, reason=reason)

    audit = tuple(sorted(records.values(), key=lambda item: (str(item["topic_id"]), int(item["topic_local_rank"]))))
    return SelectionResult(tuple(selected), audit)


def topic_diverse_enrichment_candidates(
    items: tuple[NewsItem, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int,
) -> tuple[NewsItem, ...]:
    """Choose enrichment targets round-robin by topic, not global score."""

    by_topic: dict[str, list[NewsItem]] = {topic.id: [] for topic in topics if topic.enabled}
    for item in items:
        for topic_id in topic_ids_for_item(item):
            if topic_id in by_topic:
                by_topic[topic_id].append(item)
    for topic_id, values in by_topic.items():
        values.sort(key=lambda item: (-item.score, item.title))
    selected: list[NewsItem] = []
    seen: set[str] = set()
    while len(selected) < limit:
        changed = False
        for topic in topics:
            if not topic.enabled:
                continue
            values = by_topic.get(topic.id, [])
            while values and (values[0].canonical_url or values[0].evidence_id) in seen:
                values.pop(0)
            if not values:
                continue
            item = values.pop(0)
            key = item.canonical_url or item.evidence_id
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
            changed = True
            if len(selected) >= limit:
                break
        if not changed:
            break
    return tuple(selected)
