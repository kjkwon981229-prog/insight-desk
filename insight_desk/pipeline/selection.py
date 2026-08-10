from __future__ import annotations

from dataclasses import dataclass, replace

from ..domain.models import EvidenceType, NewsItem, Topic
from .clustering import StoryCluster
from .editorial import (
    EditorialAssessment,
    assess_cluster,
    assess_relevance,
    effective_title,
    why_selected,
)
from .novelty import classify_novelty
from .synthesis import is_usable_synthesis, synthesize_cluster
from .semantics import canonical_publisher


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[StoryCluster, ...]
    audit: tuple[dict[str, object], ...]
    funnel: dict[str, dict[str, int]]
    assessments: dict[str, EditorialAssessment]
    selected_reviews: tuple[dict[str, object], ...]


def topic_ids_for_item(item: NewsItem) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.matched_topic_ids or (item.topic_id,)))


def candidate_key(cluster: StoryCluster) -> str:
    representative = cluster.representative
    return representative.canonical_url or representative.content_hash or representative.evidence_id


def _headline_key(cluster: StoryCluster) -> str:
    return " ".join(effective_title(cluster.representative).casefold().split())


def _publisher_count(cluster: StoryCluster) -> int:
    return len(
        {
            canonical_publisher(item.publisher, item.source_domain)
            for item in cluster.items
            if item.publisher or item.source_domain
        }
    )


def _summary_source(cluster: StoryCluster) -> str:
    provenance = {evidence for item in cluster.items for evidence in item.provenance}
    has_metadata = EvidenceType.ENRICHED_METADATA in provenance
    has_search = EvidenceType.SEARCH_SNIPPET in provenance
    if has_metadata and has_search:
        return "mixed_evidence"
    if has_metadata:
        return "enriched_metadata"
    return "search_evidence"


def candidate_quality(cluster: StoryCluster, topic: Topic) -> float:
    """Legacy-compatible evidence-aware candidate quality helper.

    Final selection uses the separated editorial components.  This helper is
    intentionally not a global importance score; independent publishers add
    value while repeated copies have diminishing returns.
    """

    representative = cluster.representative
    publishers = _publisher_count(cluster)
    official = 5.0 if any(EvidenceType.OFFICIAL_SOURCE in item.provenance for item in cluster.items) else 0.0
    metadata = 1.0 if any(item.metadata_title or item.metadata_description for item in cluster.items) else 0.0
    diversity_bonus = min(4, publishers) * 5.0
    syndicated_penalty = min(10.0, max(0, len(cluster.items) - publishers) * 1.5)
    return round(max(0.0, representative.score) + diversity_bonus + official + metadata - syndicated_penalty, 4)


def _coverage(cluster: StoryCluster, topic_by_id: dict[str, Topic]) -> set[str]:
    covered = {cluster.topic_id}
    for item in cluster.items:
        for topic_id in topic_ids_for_item(item):
            if topic_id == cluster.topic_id:
                continue
            topic = topic_by_id.get(topic_id)
            if topic is not None and assess_relevance(StoryCluster(topic_id, (item,)), topic).passed:
                covered.add(topic_id)
    return covered


def _funnel_template() -> dict[str, int]:
    return {
        "deduplicated": 0,
        "intent_pass": 0,
        "event_pass": 0,
        "evidence_pass": 0,
        "novelty_pass": 0,
        "qualified": 0,
        "selected": 0,
    }


def _synthesis_is_editorial_ready(
    cluster: StoryCluster,
    topic: Topic,
    *,
    official_source: bool,
    event_type: str,
    event_signature: str,
) -> bool:
    headline, summary, _, _, _, _ = synthesize_cluster(
        cluster,
        topic_name=topic.name,
        trend_metrics=(),
        event_type_override=event_type,
        event_signature_override=event_signature,
    )
    return is_usable_synthesis(
        headline,
        summary,
        source_count=cluster.source_count,
        official_source=official_source,
    )


def select_clusters(
    clusters: tuple[StoryCluster, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int = 10,
    previous_signatures: tuple[str, ...] = (),
) -> SelectionResult:
    """Select only qualified events, then apply coverage and diversity.

    Ten is a maximum, never a quota.  Coverage is applied after intent,
    event, evidence, and novelty gates so a weak item cannot enter merely to
    represent a topic.
    """

    topic_by_id = {topic.id: topic for topic in topics}
    enabled_topics = tuple(topic for topic in topics if topic.enabled)
    grouped: dict[str, list[tuple[StoryCluster, EditorialAssessment]]] = {
        topic.id: [] for topic in enabled_topics
    }
    funnel: dict[str, dict[str, int]] = {topic.id: _funnel_template() for topic in enabled_topics}
    assessments: dict[str, EditorialAssessment] = {}

    for cluster in clusters:
        topic = topic_by_id.get(cluster.topic_id)
        if topic is None or not topic.enabled:
            continue
        funnel[topic.id]["deduplicated"] += 1
        provisional = assess_cluster(cluster, topic)
        novelty = classify_novelty(provisional.event_signature, previous_signatures)
        assessment = assess_cluster(cluster, topic, novelty=novelty)
        if assessment.qualified and not _synthesis_is_editorial_ready(
            cluster,
            topic,
            official_source=assessment.evidence.official,
            event_type=assessment.event.event_type,
            event_signature=assessment.event_signature,
        ):
            assessment = replace(
                assessment,
                qualified=False,
                reasons=(*assessment.reasons, "SYNTHESIS_NOT_EDITORIAL_READY"),
            )
        grouped.setdefault(topic.id, []).append((cluster, assessment))
        assessments[f"{topic.id}:{candidate_key(cluster)}"] = assessment
        if assessment.relevance.passed:
            funnel[topic.id]["intent_pass"] += 1
        if assessment.event.passed:
            funnel[topic.id]["event_pass"] += 1
        if assessment.evidence.passed or "SUPPORTED_SINGLE_SOURCE" in assessment.reasons:
            funnel[topic.id]["evidence_pass"] += 1
        if novelty != "UNCHANGED":
            funnel[topic.id]["novelty_pass"] += 1
        if assessment.qualified:
            funnel[topic.id]["qualified"] += 1

    for values in grouped.values():
        values.sort(key=lambda value: (-value[1].final_score, effective_title(value[0].representative)))

    selected: list[tuple[StoryCluster, EditorialAssessment, str, float]] = []
    selected_keys: set[str] = set()
    selected_headline_keys: set[str] = set()
    selected_coverage: set[str] = set()
    topic_counts: dict[str, int] = {topic.id: 0 for topic in enabled_topics}
    records: dict[tuple[str, str], dict[str, object]] = {}

    qualifying_topic_ids = {
        topic_id for topic_id, values in grouped.items() if any(assessment.qualified for _, assessment in values)
    }
    capped = len(qualifying_topic_ids) >= 3

    def local_rank(topic_id: str, key: str) -> int:
        return next(
            (index for index, (cluster, _) in enumerate(grouped.get(topic_id, ()), 1) if candidate_key(cluster) == key),
            0,
        )

    def write_record(
        cluster: StoryCluster,
        assessment: EditorialAssessment,
        *,
        selected_value: bool,
        reason: str,
        penalty: float = 0.0,
    ) -> None:
        topic = topic_by_id[cluster.topic_id]
        key = candidate_key(cluster)
        records[(cluster.topic_id, key)] = {
            "candidate_key": key,
            "topic_id": cluster.topic_id,
            "topic_name": topic.name,
            "topic_local_rank": local_rank(cluster.topic_id, key),
            "qualifying": assessment.qualified,
            "selected": selected_value,
            "reason": reason,
            "saturation_penalty": round(penalty, 3),
            "conditional": topic.conditional,
            "source_count": cluster.source_count,
            "source_diversity": assessment.evidence.publisher_diversity,
            "retrieval_channels": sorted({channel for item in cluster.items for channel in item.retrieval_channels}),
            "intent_relevance": assessment.relevance.score,
            "event_type": assessment.event.event_type,
            "event_significance": assessment.event.significance,
            "evidence_strength": assessment.evidence.strength,
            "certainty_gate": "supported_single_source" if "SUPPORTED_SINGLE_SOURCE" in assessment.reasons else "multi_or_official",
            "novelty": assessment.novelty,
            "event_signature": assessment.event_signature,
            "final_score": assessment.final_score,
            "why_selected": list(why_selected(assessment)) if selected_value else [],
            "selection_reasons": list(assessment.reasons),
        }

    def choose(cluster: StoryCluster, assessment: EditorialAssessment, reason: str, penalty: float = 0.0) -> None:
        key = candidate_key(cluster)
        headline_key = _headline_key(cluster)
        if key in selected_keys or headline_key in selected_headline_keys or len(selected) >= max(0, limit):
            return
        selected.append((cluster, assessment, reason, penalty))
        selected_keys.add(key)
        selected_headline_keys.add(headline_key)
        topic_counts[cluster.topic_id] = topic_counts.get(cluster.topic_id, 0) + 1
        selected_coverage.update(_coverage(cluster, topic_by_id))
        funnel[cluster.topic_id]["selected"] += 1
        write_record(cluster, assessment, selected_value=True, reason=reason, penalty=penalty)

    # One best qualified candidate gets a representation opportunity for each
    # interest that actually has a qualifying event. A shared event can cover
    # multiple interests without being rendered twice.
    for topic in enabled_topics:
        if topic.id in selected_coverage or len(selected) >= limit:
            continue
        for cluster, assessment in grouped.get(topic.id, ()):
            if (
                assessment.qualified
                and candidate_key(cluster) not in selected_keys
                and _headline_key(cluster) not in selected_headline_keys
            ):
                choose(cluster, assessment, "quality coverage floor")
                break

    # Merge cross-topic views by canonical candidate key. Choose the strongest
    # topic-local assessment as the primary editorial view.
    candidates: dict[str, tuple[StoryCluster, EditorialAssessment]] = {}
    for topic_id, values in grouped.items():
        for cluster, assessment in values:
            if not assessment.qualified:
                continue
            key = candidate_key(cluster)
            existing = candidates.get(key)
            if existing is None or assessment.final_score > existing[1].final_score:
                candidates[key] = (cluster, assessment)

    while len(selected) < max(0, limit):
        available: list[tuple[float, StoryCluster, EditorialAssessment, float]] = []
        for key, (cluster, assessment) in candidates.items():
            if key in selected_keys or _headline_key(cluster) in selected_headline_keys:
                continue
            topic = topic_by_id[cluster.topic_id]
            current_count = topic_counts.get(cluster.topic_id, 0)
            if capped and current_count >= topic.selection_cap:
                continue
            saturation_penalty = min(18.0, current_count * 7.0)
            adjacency_penalty = 5.0 if selected and selected[-1][0].topic_id == cluster.topic_id else 0.0
            if len(selected) >= 2 and selected[-1][0].topic_id == selected[-2][0].topic_id == cluster.topic_id:
                adjacency_penalty += 8.0
            theme_penalty = 0.0
            title_tokens = set(effective_title(cluster.representative).casefold().split())
            for existing, _, _, _ in selected:
                existing_tokens = set(effective_title(existing.representative).casefold().split())
                if len(title_tokens & existing_tokens) >= 2:
                    theme_penalty += 4.0
            adjusted = assessment.final_score - saturation_penalty - adjacency_penalty - min(8.0, theme_penalty)
            available.append((adjusted, cluster, assessment, saturation_penalty + adjacency_penalty + theme_penalty))
        if not available:
            break
        _, cluster, assessment, penalty = max(
            available,
            key=lambda value: (value[0], value[2].final_score, -len(selected), effective_title(value[1].representative)),
        )
        choose(cluster, assessment, "quality + diversity", penalty)

    # Final numbering must be an actual editorial ranking, not config order or
    # coverage insertion order.
    selected.sort(key=lambda value: (-value[1].final_score, effective_title(value[0].representative)))

    for topic_id, values in grouped.items():
        for cluster, assessment in values:
            key = (topic_id, candidate_key(cluster))
            if key in records:
                continue
            if not assessment.qualified:
                reason = "editorial quality gate"
            elif candidate_key(cluster) in selected_keys:
                reason = "cross-topic event already selected"
            elif capped and topic_counts.get(topic_id, 0) >= topic_by_id[topic_id].selection_cap:
                reason = "topic saturation cap"
            elif _headline_key(cluster) in selected_headline_keys:
                reason = "duplicate rendered headline"
            else:
                reason = "remaining slot"
            write_record(cluster, assessment, selected_value=False, reason=reason)

    selected_reviews: list[dict[str, object]] = []
    for rank, (cluster, assessment, reason, _) in enumerate(selected, 1):
        selected_reviews.append(
            {
                "rank": rank,
                "topic_id": cluster.topic_id,
                "topic": topic_by_id[cluster.topic_id].name,
                "headline": effective_title(cluster.representative),
                "source_count": cluster.source_count,
                "publisher_diversity": assessment.evidence.publisher_diversity,
                "metadata_enriched_count": sum(
                    EvidenceType.ENRICHED_METADATA in item.provenance for item in cluster.items
                ),
                "retrieval_channels": sorted({channel for item in cluster.items for channel in item.retrieval_channels}),
                "query": cluster.representative.query,
                "intent_relevance": assessment.relevance.score,
                "event_type": assessment.event.event_type,
                "event_significance": assessment.event.significance,
                "concrete_fact_count": assessment.event.concrete_fact_count,
                "evidence_strength": assessment.evidence.strength,
                "official_source": assessment.evidence.official,
                "metadata_complete": assessment.evidence.metadata_complete,
                "conflict_state": assessment.evidence.conflict_state,
                "certainty": (
                    "confirmed"
                    if assessment.evidence.official or assessment.evidence.publisher_diversity >= 2
                    else "supported_single_source"
                ),
                "novelty": assessment.novelty,
                "event_signature": assessment.event_signature,
                "final_score": assessment.final_score,
                "why_selected": list(why_selected(assessment)),
                "selection_reason": reason,
                "summary_source": _summary_source(cluster),
            }
        )

    selected_clusters = tuple(cluster for cluster, _, _, _ in selected)
    return SelectionResult(
        selected=selected_clusters,
        audit=tuple(
            sorted(
                records.values(),
                key=lambda item: (str(item["topic_id"]), int(item["topic_local_rank"])),
            )
        ),
        funnel=funnel,
        assessments={candidate_key(cluster): assessment for cluster, assessment, _, _ in selected},
        selected_reviews=tuple(selected_reviews),
    )


def topic_diverse_enrichment_candidates(
    items: tuple[NewsItem, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int,
) -> tuple[NewsItem, ...]:
    """Choose cheap-intent-passing enrichment targets round-robin by topic."""

    by_topic: dict[str, list[tuple[NewsItem, float]]] = {topic.id: [] for topic in topics if topic.enabled}
    for item in items:
        for topic_id in topic_ids_for_item(item):
            topic = next((topic for topic in topics if topic.id == topic_id and topic.enabled), None)
            if topic is None:
                continue
            assessment = assess_relevance(StoryCluster(topic_id, (item,)), topic)
            if assessment.passed:
                by_topic[topic_id].append((item, assessment.score))
    for values in by_topic.values():
        values.sort(key=lambda value: (-value[1], -value[0].score, effective_title(value[0])))
    selected: list[NewsItem] = []
    seen: set[str] = set()
    while len(selected) < limit:
        changed = False
        for topic in topics:
            if not topic.enabled:
                continue
            values = by_topic.get(topic.id, [])
            while values and (values[0][0].canonical_url or values[0][0].evidence_id) in seen:
                values.pop(0)
            if not values:
                continue
            item, _ = values.pop(0)
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


def cap_topic_candidates(
    items: tuple[NewsItem, ...],
    topics: tuple[Topic, ...],
) -> tuple[NewsItem, ...]:
    """Enforce the configured merged topic-pool upper bound fairly."""

    enabled = tuple(topic for topic in topics if topic.enabled)
    by_topic: dict[str, list[NewsItem]] = {topic.id: [] for topic in enabled}
    for item in items:
        for topic_id in topic_ids_for_item(item):
            if topic_id in by_topic:
                by_topic[topic_id].append(item)
    for values in by_topic.values():
        values.sort(key=lambda item: (-item.score, effective_title(item)))
    topic_caps = {topic.id: topic.candidate_budget for topic in enabled}
    counts = {topic.id: 0 for topic in enabled}
    selected: list[NewsItem] = []
    seen: set[str] = set()
    positions = {topic.id: 0 for topic in enabled}
    changed = True
    while changed:
        changed = False
        for topic in enabled:
            if counts[topic.id] >= topic.candidate_budget:
                continue
            values = by_topic[topic.id]
            while positions[topic.id] < len(values):
                item = values[positions[topic.id]]
                positions[topic.id] += 1
                key = item.canonical_url or item.content_hash or item.evidence_id
                if key in seen:
                    continue
                matched = topic_ids_for_item(item)
                if any(
                    other_id in topic_caps and counts.get(other_id, 0) >= topic_caps[other_id]
                    for other_id in matched
                ):
                    continue
                seen.add(key)
                selected.append(item)
                for other_id in matched:
                    if other_id in counts:
                        counts[other_id] += 1
                changed = True
                break
    return tuple(selected)
