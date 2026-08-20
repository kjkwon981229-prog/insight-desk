from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from ..domain.models import EvidenceType, NewsItem, Topic
from .clustering import StoryCluster
from .editorial import (
    EditorialAssessment,
    assess_cluster,
    assess_event,
    assess_relevance,
    assess_semantic_relevance,
    best_headline_item,
    daily_freshness_reasons,
    effective_title,
    event_owned_items,
    why_selected,
)
from .novelty import classify_novelty
from .semantics import (
    CanonicalEvent,
    canonical_publisher,
    explicit_unclassified_event_signal,
    metric_summary_preserves_entity_binding,
    same_event_lifecycle,
    summary_preserves_primary_focus,
)
from .synthesis import (
    _event_relation_fact,
    _relation_summary_preserves_fact,
    earnings_summary_preserves_fact_binding,
    industry_summary_preserves_fact_binding,
    is_usable_synthesis,
    synthesize_cluster,
)


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[StoryCluster, ...]
    audit: tuple[dict[str, object], ...]
    funnel: dict[str, dict[str, int]]
    assessments: dict[str, EditorialAssessment]
    selected_reviews: tuple[dict[str, object], ...]
    enrichment_candidates: tuple[StoryCluster, ...] = ()
    strong_rejected_candidates: int = 0
    filter_collapse: bool = False


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
            if topic is not None and assess_semantic_relevance(item, topic).passed:
                covered.add(topic_id)
    return covered


def _funnel_template() -> dict[str, int]:
    return {
        "deduplicated": 0,
        "intent_pass": 0,
        "event_pass": 0,
        "evidence_pass": 0,
        "novelty_pass": 0,
        "freshness_pass": 0,
        "qualified": 0,
        "selected": 0,
        "synthesis_veto": 0,
        "strong_rejected": 0,
    }


def _is_unclassified_event_recall_risk(
    cluster: StoryCluster,
    assessment: EditorialAssessment,
    *,
    novelty: str,
    freshness_reasons: tuple[str, ...],
) -> bool:
    """Expose a concrete OTHER event to diagnostics without selecting it."""

    if (
        not assessment.relevance.passed
        or assessment.event.event_type != "OTHER"
        or novelty == "UNCHANGED"
        or freshness_reasons
        or assessment.evidence.conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}
    ):
        return False
    title = effective_title(best_headline_item(cluster.items))
    return explicit_unclassified_event_signal(title)


def _is_strong_rejected(assessment: EditorialAssessment) -> bool:
    """Detect a complete owned event lost by an editorial gate.

    The signal is fact-based, never a selected-story quota.  In particular,
    an explicit source-owned subject/action/object relation remains visible
    if a future event, ownership, or synthesis regression drops it before the
    old downstream-only diagnostic can see it.
    """

    synthesis_vetoed_qualified = (
        "QUALIFIED" in assessment.reasons
        and "SYNTHESIS_FACT_LOSS" in assessment.reasons
        and "SYNTHESIS_NOT_EDITORIAL_READY" in assessment.reasons
    )
    upstream_passed = (
        assessment.relevance.passed
        and assessment.event.passed
        and (assessment.evidence.passed or "SUPPORTED_SINGLE_SOURCE" in assessment.reasons)
        and assessment.novelty != "UNCHANGED"
        and assessment.evidence.conflict_state in {"NO_CONFLICT", "CONFIRMED_MATCH"}
        and "FRESHNESS_FAILED" not in assessment.reasons
    )
    canonical = assessment.event.canonical_event
    # "Strong" means the event already owns a complete, typed fact bundle.
    # A ratio-only headline that still needs its article lead is an enrichment
    # gap, not evidence that synthesis discarded a complete event.
    canonical_facts_complete = bool(canonical and canonical.fact_complete)
    owned_relation_complete = bool(
        canonical
        and canonical_facts_complete
        and canonical.representative_evidence_id
        and canonical.representative_evidence_id in canonical.evidence_owner_ids
        and any(fact.role == "EVENT_RELATION" for fact in canonical.facts)
    )
    upstream_owned_relation_lost = bool(
        assessment.relevance.passed
        and owned_relation_complete
        and not assessment.qualified
        and assessment.novelty != "UNCHANGED"
        and assessment.evidence.conflict_state in {"NO_CONFLICT", "CONFIRMED_MATCH"}
        and "FRESHNESS_FAILED" not in assessment.reasons
        and "AUTHORITY_REQUIRED_UNVERIFIED" not in assessment.reasons
        and "LOW_VALUE_EVENT" not in assessment.reasons
        and any(
            reason in assessment.reasons
            for reason in (
                "EVENT_ACTION_CONTRACT_FAILED",
                "FACT_OWNERSHIP_UNSUPPORTED",
                "SYNTHESIS_FACT_LOSS",
            )
        )
        and assessment.event.concrete_fact_count >= 3
        and assessment.event.significance >= 60.0
    )
    if upstream_owned_relation_lost:
        return True
    if synthesis_vetoed_qualified:
        return bool(
            upstream_passed
            and (canonical is None or not canonical.needs_enrichment)
            and not assessment.qualified
            and assessment.event.concrete_fact_count >= 3
            and assessment.event.significance >= 60.0
            and assessment.final_score >= 45.0
        )
    return bool(
        upstream_passed
        and canonical_facts_complete
        and not assessment.qualified
        and assessment.evidence.metadata_complete
        and assessment.event.concrete_fact_count >= 3
        and assessment.event.significance >= 60.0
        and assessment.final_score >= 45.0
    )


def _predicate_rejection_reason(assessment: EditorialAssessment) -> str:
    for reason in (
        "RELEVANCE_FAILED",
        "LOW_VALUE_EVENT",
        "EVENT_ACTION_CONTRACT_FAILED",
        "EVENT_OWNERSHIP_FAILED",
        "FACT_OWNERSHIP_UNSUPPORTED",
        "AUTHORITY_REQUIRED_UNVERIFIED",
        "AUTHORITY_CONFLICT",
        "EVIDENCE_FAILED",
        "NOVELTY_UNCHANGED",
        "FRESHNESS_FAILED",
        "SYNTHESIS_FACT_LOSS",
        "SYNTHESIS_NOT_EDITORIAL_READY",
        "GENERIC_HEADLINE",
        "GENERIC_SUMMARY",
        "SINGLE_SOURCE_METRIC_WITHOUT_TRUSTED_LEAD",
    ):
        if reason in assessment.reasons:
            return reason
    return "EDITORIAL_QUALITY_GATE"


def _synthesis_is_editorial_ready(
    cluster: StoryCluster,
    topic: Topic,
    *,
    official_source: bool,
    event_type: str,
    event_signature: str,
    canonical_event: CanonicalEvent | None = None,
) -> bool:
    headline, summary, _, _, facts, _ = synthesize_cluster(
        cluster,
        topic_name=topic.name,
        trend_metrics=(),
        event_type_override=event_type,
        event_signature_override=event_signature,
        canonical_event_override=canonical_event,
    )
    if event_type in {"MARKET", "MARKET_MOVE", "STATISTIC", "EARNINGS"} and not metric_summary_preserves_entity_binding(
        headline,
        summary,
    ):
        return False
    if event_type == "EARNINGS" and not earnings_summary_preserves_fact_binding(headline, summary):
        return False
    if event_type == "INDUSTRY_CHANGE" and canonical_event is not None and not industry_summary_preserves_fact_binding(
        headline,
        summary,
        canonical_event.facts,
    ):
        return False
    if not summary_preserves_primary_focus(summary, facts.primary_focus_terms):
        return False
    relation_fact = _event_relation_fact(canonical_event.facts) if canonical_event is not None else None
    return is_usable_synthesis(
        headline,
        summary,
        source_count=cluster.source_count,
        official_source=official_source,
        relation_fact=relation_fact,
        relation_fact_preserved=bool(
            relation_fact
            and _relation_summary_preserves_fact(summary, headline, relation_fact)
        ),
    )


_CANONICAL_CONVERGENCE_TYPES = frozenset(
    {
        "SPORTS_INTERRUPTION",
        "SPORTS_RESULT",
        "RECRUITMENT_COMPETITION",
        "EARNINGS",
        "MARKET",
        "MARKET_MOVE",
        "STATISTIC",
    }
)


def _converge_canonical_clusters(
    clusters: tuple[StoryCluster, ...],
    topic_by_id: dict[str, Topic],
) -> tuple[StoryCluster, ...]:
    """Combine lexical clusters that resolve to one high-confidence event.

    Initial clustering remains conservative to prevent snippet-tail
    over-merging.  Once the event family and bound facts are known, a narrow
    second pass can safely converge equivalent representations (for example
    a heat-interruption headline and its resumption update).
    """

    result: list[StoryCluster] = []
    by_key: dict[tuple[str, str], int] = {}
    lifecycle_groups: dict[int, list[CanonicalEvent]] = {}
    for cluster in clusters:
        topic = topic_by_id.get(cluster.topic_id)
        if topic is None:
            result.append(cluster)
            continue
        event = assess_event(cluster, topic)
        canonical = event.canonical_event
        signature = canonical.event_signature if canonical is not None else ""
        if (
            event.event_type not in _CANONICAL_CONVERGENCE_TYPES
            or not signature
            or (canonical is not None and canonical.conflict_state != "NO_CONFLICT")
        ):
            result.append(cluster)
            continue
        key = (cluster.topic_id, signature)
        if event.event_type == "SPORTS_INTERRUPTION" and canonical is not None:
            index = next(
                (
                    candidate_index
                    for candidate_index, members in lifecycle_groups.items()
                    if result[candidate_index].topic_id == cluster.topic_id
                    and all(same_event_lifecycle(canonical, member) for member in members)
                ),
                None,
            )
        else:
            index = by_key.get(key)
        if index is None:
            index = len(result)
            result.append(cluster)
            if event.event_type == "SPORTS_INTERRUPTION" and canonical is not None:
                lifecycle_groups[index] = [canonical]
            else:
                by_key[key] = index
            continue
        existing = result[index]
        seen: set[str] = set()
        items: list[NewsItem] = []
        for item in (*existing.items, *cluster.items):
            item_key = item.canonical_url or item.content_hash or item.evidence_id
            if item_key in seen:
                continue
            seen.add(item_key)
            items.append(item)
        result[index] = StoryCluster(cluster.topic_id, tuple(items))
        if event.event_type == "SPORTS_INTERRUPTION" and canonical is not None:
            lifecycle_groups[index].append(canonical)
    return tuple(result)


def select_clusters(
    clusters: tuple[StoryCluster, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int = 10,
    previous_signatures: tuple[str, ...] = (),
    now: datetime | None = None,
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
    enrichment_candidates: list[StoryCluster] = []
    strong_rejected_candidates = 0

    clusters = _converge_canonical_clusters(clusters, topic_by_id)

    for cluster in clusters:
        topic = topic_by_id.get(cluster.topic_id)
        if topic is None or not topic.enabled:
            continue
        funnel[topic.id]["deduplicated"] += 1
        provisional = assess_cluster(cluster, topic)
        novelty = classify_novelty(provisional.event_signature, previous_signatures)
        assessment = assess_cluster(cluster, topic, novelty=novelty)
        freshness_reasons = daily_freshness_reasons(
            cluster,
            assessment.event,
            now=now,
            novelty=novelty,
        )
        if freshness_reasons:
            assessment = replace(
                assessment,
                qualified=False,
                reasons=(*assessment.reasons, *freshness_reasons),
            )
        if (assessment.qualified or (assessment.relevance.passed and assessment.event.passed)) and not _synthesis_is_editorial_ready(
            cluster,
            topic,
            official_source=assessment.evidence.official,
            event_type=assessment.event.event_type,
            event_signature=assessment.event_signature,
            canonical_event=assessment.event.canonical_event,
        ):
            assessment = replace(
                assessment,
                qualified=False,
                reasons=(*assessment.reasons, "SYNTHESIS_NOT_EDITORIAL_READY", "SYNTHESIS_FACT_LOSS"),
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
        if not freshness_reasons:
            funnel[topic.id]["freshness_pass"] += 1
        if assessment.qualified:
            funnel[topic.id]["qualified"] += 1
        if "SYNTHESIS_NOT_EDITORIAL_READY" in assessment.reasons:
            funnel[topic.id]["synthesis_veto"] += 1
        if _is_unclassified_event_recall_risk(
            cluster,
            assessment,
            novelty=novelty,
            freshness_reasons=freshness_reasons,
        ) or _is_strong_rejected(assessment):
            strong_rejected_candidates += 1
            funnel[topic.id]["strong_rejected"] += 1
            enrichment_candidates.append(cluster)
        elif (
            "SYNTHESIS_NOT_EDITORIAL_READY" in assessment.reasons
            and assessment.event.canonical_event is not None
            and assessment.event.canonical_event.needs_enrichment
        ):
            enrichment_candidates.append(cluster)

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
        owned_items = event_owned_items(cluster, assessment.event.canonical_event)
        owned_cluster = StoryCluster(cluster.topic_id, owned_items or cluster.items)
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
            "source_count": owned_cluster.source_count,
            "source_diversity": assessment.evidence.publisher_diversity,
            "retrieval_channels": sorted({channel for item in cluster.items for channel in item.retrieval_channels}),
            "retrieval_queries": sorted({
                query
                for item in cluster.items
                for query in (item.retrieval_queries or (item.query,))
                if query
            }),
            "intent_relevance": assessment.relevance.score,
            "event_type": assessment.event.event_type,
            "event_significance": assessment.event.significance,
            "evidence_strength": assessment.evidence.strength,
            "certainty_gate": "supported_single_source" if "SUPPORTED_SINGLE_SOURCE" in assessment.reasons else "multi_or_official",
            "novelty": assessment.novelty,
            "event_signature": assessment.event_signature,
            "canonical_event_id": (
                assessment.event.canonical_event.canonical_event_id
                if assessment.event.canonical_event is not None
                else assessment.event_signature
            ),
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
                reason = _predicate_rejection_reason(assessment)
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
        owned_items = event_owned_items(cluster, assessment.event.canonical_event)
        owned_cluster = StoryCluster(cluster.topic_id, owned_items or cluster.items)
        owned_representative = best_headline_item(owned_cluster.items)
        selected_reviews.append(
            {
                "rank": rank,
                "topic_id": cluster.topic_id,
                "topic": topic_by_id[cluster.topic_id].name,
                "headline": effective_title(owned_representative),
                "source_count": owned_cluster.source_count,
                "publisher_diversity": assessment.evidence.publisher_diversity,
                "metadata_enriched_count": sum(
                    EvidenceType.ENRICHED_METADATA in item.provenance
                    for item in owned_cluster.items
                ),
                "retrieval_channels": sorted(
                    {channel for item in owned_cluster.items for channel in item.retrieval_channels}
                ),
                "retrieval_queries": sorted({
                    query
                    for item in owned_cluster.items
                    for query in (item.retrieval_queries or (item.query,))
                    if query
                }),
                "query": owned_representative.query,
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
                    if assessment.evidence.official or assessment.evidence.corroborated
                    else "supported_single_source"
                ),
                "novelty": assessment.novelty,
                "event_signature": assessment.event_signature,
                "canonical_event_id": (
                    assessment.event.canonical_event.canonical_event_id
                    if assessment.event.canonical_event is not None
                    else assessment.event_signature
                ),
                "fixture_id": (
                    assessment.event.canonical_event.fixture_id
                    if assessment.event.canonical_event is not None
                    else ""
                ),
                "final_score": assessment.final_score,
                "why_selected": list(why_selected(assessment)),
                "selection_reason": reason,
                "summary_source": _summary_source(owned_cluster),
                "representative_evidence_id": owned_representative.evidence_id,
                "event_owner_ids": list(
                    assessment.event.canonical_event.evidence_owner_ids
                    if assessment.event.canonical_event is not None
                    else ()
                ),
            }
        )

    selected_clusters = tuple(cluster for cluster, _, _, _ in selected)
    filter_collapse = not selected_clusters and strong_rejected_candidates > 0
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
        enrichment_candidates=tuple(enrichment_candidates),
        strong_rejected_candidates=strong_rejected_candidates,
        filter_collapse=filter_collapse,
    )


def topic_diverse_enrichment_candidates(
    items: tuple[NewsItem, ...],
    topics: tuple[Topic, ...],
    *,
    limit: int,
    priority_clusters: tuple[object, ...] = (),
) -> tuple[NewsItem, ...]:
    """Choose bounded enrichment targets with a preliminary-selection hint.

    Metadata enrichment happens before the authoritative and final editorial
    gates, so a fixed topic round-robin can starve a candidate that the
    preliminary selector already considers worth reviewing.  Prefer those
    candidates first, then use the existing topic-diverse fill.  ``limit`` is
    still a hard upper bound and no extra network request is implied.
    """

    by_topic: dict[str, list[tuple[NewsItem, float]]] = {topic.id: [] for topic in topics if topic.enabled}
    for item in items:
        for topic_id in topic_ids_for_item(item):
            topic = next((topic for topic in topics if topic.id == topic_id and topic.enabled), None)
            if topic is None:
                continue
            assessment = assess_semantic_relevance(item, topic)
            if assessment.passed:
                by_topic[topic_id].append((item, assessment.score))
    for values in by_topic.values():
        values.sort(key=lambda value: (-value[1], -value[0].score, effective_title(value[0])))
    selected: list[NewsItem] = []
    seen: set[str] = set()

    by_key = {
        item.canonical_url or item.content_hash or item.evidence_id: item
        for item in items
    }
    for cluster in priority_clusters:
        if len(selected) >= limit:
            break
        for item in getattr(cluster, "items", ()):
            key = item.canonical_url or item.content_hash or item.evidence_id
            if key in seen or key not in by_key:
                continue
            if any(
                topic_id in by_topic and assess_semantic_relevance(item, next(topic for topic in topics if topic.id == topic_id)).passed
                for topic_id in topic_ids_for_item(item)
            ):
                selected.append(by_key[key])
                seen.add(key)
                break
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
                semantic_matched = tuple(
                    topic_id
                    for topic_id in matched
                    if topic_id in topic_caps
                    and assess_semantic_relevance(
                        item,
                        next(topic for topic in enabled if topic.id == topic_id),
                    ).passed
                )
                if not semantic_matched:
                    continue
                available_matched = tuple(
                    topic_id
                    for topic_id in semantic_matched
                    if counts.get(topic_id, 0) < topic_caps[topic_id]
                )
                if not available_matched:
                    continue
                seen.add(key)
                # Raw retrieval provenance remains on the item; matched topic
                # ids here are semantic attributions that may consume budget.
                # A full incidental topic must not discard a shared event that
                # still has budget in another semantically matched topic.
                selected.append(replace(item, matched_topic_ids=available_matched))
                for other_id in available_matched:
                    if other_id in counts:
                        counts[other_id] += 1
                changed = True
                break
    return tuple(selected)
