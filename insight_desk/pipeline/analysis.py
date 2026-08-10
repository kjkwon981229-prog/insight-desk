from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from ..collectors.enrichment import EnrichmentReport
from ..domain.models import (
    Briefing,
    CollectorStatus,
    EvidenceType,
    NewsItem,
    RunState,
    RunStatus,
    Story,
    Topic,
    TrendMetric,
    to_jsonable,
)
from .clustering import StoryCluster
from .editorial import assess_relevance, effective_lead, effective_title, why_selected
from .scoring import score_clusters
from .selection import candidate_key, select_clusters
from .synthesis import synthesize_cluster
from .trend_metrics import effective_trend_state


def _topic_name(topic_id: str, topics: tuple[Topic, ...]) -> str:
    return next((topic.name for topic in topics if topic.id == topic_id), topic_id)


def _trend_for_topic(topic_id: str, metrics: tuple[TrendMetric, ...]) -> tuple[TrendMetric, ...]:
    return tuple(metric for metric in metrics if metric.topic_id == topic_id)


def _trend_label(topic_id: str, metrics: tuple[TrendMetric, ...]) -> str:
    relevant = _trend_for_topic(topic_id, metrics)
    if not relevant:
        return ""
    states = tuple(effective_trend_state(metric) for metric in relevant)
    rising = "RISE" in states
    falling = "FALL" in states
    if rising and falling:
        return "검색 관심 · 혼조"
    if rising:
        return "검색 관심 · 상승"
    if falling:
        return "검색 관심 · 둔화"
    if "INSUFFICIENT_COMPARISON" in states:
        return "검색 관심 · 비교 부족"
    return "검색 관심 · 큰 변화 없음"


def _story_trend_label(cluster: StoryCluster, metrics: tuple[TrendMetric, ...]) -> str:
    """Attach a trend only when its group name matches the story evidence."""

    return _trend_label(cluster.topic_id, _story_trend_matches(cluster, metrics))


def _story_trend_matches(
    cluster: StoryCluster, metrics: tuple[TrendMetric, ...]
) -> tuple[TrendMetric, ...]:
    text = " ".join(
        value
        for item in cluster.items
        for value in (
            effective_title(item),
            effective_lead(item),
            *(
                authority.title
                for authority in getattr(item, "authoritative_evidence", ())
                if getattr(authority, "title", "")
            ),
        )
        if value
    ).casefold()
    matched = tuple(
        metric
        for metric in _trend_for_topic(cluster.topic_id, metrics)
        if metric.group_name.casefold() in text or metric.group_id.casefold() in text
    )
    return matched


def _trend_overview(metrics: tuple[TrendMetric, ...]) -> str:
    if not metrics:
        return "검색 관심 · 비교 부족"
    states = tuple(effective_trend_state(metric) for metric in metrics)
    rising = states.count("RISE")
    falling = states.count("FALL")
    if rising and falling:
        return "검색 관심 · 혼조"
    if rising:
        return f"검색 관심 · {rising}개 그룹 상승"
    if falling:
        return f"검색 관심 · {falling}개 그룹 둔화"
    if "INSUFFICIENT_COMPARISON" in states:
        return "검색 관심 · 비교 부족"
    return "검색 관심 · 큰 변화 없음"


def _story_topic_ids(cluster: StoryCluster, topics: tuple[Topic, ...]) -> tuple[str, ...]:
    """Keep only cross-topic attributions supported by topic relevance.

    Deduplication preserves every retrieval topic so a genuinely shared event
    can cover multiple interests.  That provenance is not, by itself, proof
    that the story belongs to every topic, though: a query such as ``한화
    경기`` can merge an economy article mentioning ``한화에어로스페이스``.
    Reassess each additional topic against the item evidence before exposing
    the attribution in the briefing.
    """

    topic_by_id = {topic.id: topic for topic in topics}
    matched: list[str] = [cluster.topic_id]
    for item in cluster.items:
        for topic_id in item.matched_topic_ids or (item.topic_id,):
            if topic_id == cluster.topic_id or topic_id in matched:
                continue
            topic = topic_by_id.get(topic_id)
            if topic is None:
                continue
            if assess_relevance(StoryCluster(topic_id, (item,)), topic).passed:
                matched.append(topic_id)
    return tuple(matched)


def build_briefing(
    *,
    state: RunState,
    topics: tuple[Topic, ...],
    news: tuple[NewsItem, ...],
    clusters: tuple[StoryCluster, ...],
    trend_metrics: tuple[TrendMetric, ...],
    generated_at: datetime,
    enrichment: EnrichmentReport | None = None,
    previous_signatures: tuple[str, ...] = (),
    retrieval_funnel: dict[str, dict[str, int]] | None = None,
    authoritative_audit: tuple[dict[str, object], ...] = (),
) -> Briefing:
    topic_by_id = {topic.id: topic for topic in topics}
    # score_clusters is retained as a candidate-quality ordering. It is not the
    # public lineup anymore; selection applies coverage and diversity rules.
    ranked_clusters = score_clusters(clusters)
    selection = select_clusters(
        ranked_clusters,
        topics,
        limit=10,
        previous_signatures=previous_signatures,
    )
    editorial_health = "FILTER_COLLAPSE" if selection.filter_collapse else "OK"
    if selection.filter_collapse:
        state = replace(state, status=RunStatus.FILTER_COLLAPSE, publish=False)
    stories: list[Story] = []
    selected_reviews = tuple(selection.selected_reviews)
    story_trend_matches: list[tuple[TrendMetric, ...]] = []
    for cluster in selection.selected:
        topic_name = topic_by_id.get(cluster.topic_id, Topic(cluster.topic_id, cluster.topic_id, True, False, 50, ())).name
        assessment = selection.assessments.get(candidate_key(cluster))
        if assessment is None:
            continue
        provenance = tuple(
            dict.fromkeys(
                evidence_type
                for item in cluster.items
                for evidence_type in item.provenance
            )
        )
        metadata_count = sum(
            EvidenceType.ENRICHED_METADATA in item.provenance for item in cluster.items
        )
        headline, summary, evidence_summary, watch_next, facts, certainty = synthesize_cluster(
            cluster,
            topic_name=topic_name,
            trend_metrics=trend_metrics,
            event_type_override=assessment.event.event_type,
            event_signature_override=assessment.event_signature,
            conflict_state_override=assessment.evidence.conflict_state,
        )
        stories.append(
            Story(
                topic_id=cluster.topic_id,
                topic_name=topic_name,
                title=headline,
                summary=summary,
                why_it_matters=evidence_summary,
                trend_relationship=_story_trend_label(cluster, trend_metrics),
                industry_impact="",
                investment_relevance="",
                watch_next=watch_next,
                evidence_ids=tuple(item.evidence_id for item in cluster.items),
                certainty=certainty,
                score=assessment.final_score,
                source_count=cluster.source_count,
                provenance=provenance,
                metadata_enriched_count=metadata_count,
                facts=facts,
                matched_topic_ids=_story_topic_ids(cluster, topics),
                novelty=assessment.novelty,
                why_selected=why_selected(assessment),
                intent_relevance=assessment.relevance.score,
                event_significance=assessment.event.significance,
                evidence_strength=assessment.evidence.strength,
                information_completeness=assessment.completeness,
                editorial_score=assessment.final_score,
                event_signature=assessment.event_signature,
            )
        )
        story_trend_matches.append(_story_trend_matches(cluster, trend_metrics))

    represented_ids = tuple(dict.fromkeys(topic_id for story in stories for topic_id in (story.matched_topic_ids or (story.topic_id,))))
    represented_names = tuple(topic_by_id[topic_id].name for topic_id in represented_ids if topic_id in topic_by_id)
    if stories:
        lines = [
            f"오늘 확인할 가치가 있는 {len(stories)}개 변화를 {len(represented_names)}개 관심사에서 추렸다.",
            _trend_overview(trend_metrics),
            " · ".join(represented_names) if represented_names else "선택한 관심사에서 확인한 흐름",
        ]
    else:
        lines = [
            "오늘은 표시 기준을 넘은 변화가 없다.",
            _trend_overview(trend_metrics),
            "조건을 충족한 관심사만 표시했다.",
        ]

    report = enrichment or EnrichmentReport()
    limitations = [
        "뉴스 근거는 NAVER 검색 결과의 제목·요약·링크를 기본으로 사용했다.",
        "Search Trend는 원시 검색량이 아닌 상대 관심지수이며, 동일 키워드 그룹 내부의 직전 구간 변화만 비교했다.",
        f"데이터 기준 시각은 {generated_at.isoformat(timespec='seconds')}이며, 기사 게시 시각과 사건 발생 시각은 별도 개념이다.",
    ]
    if report.attempted:
        limitations.append(
            f"상위 기사 원문 공개 metadata는 {report.attempted}건 중 {report.succeeded}건을 선택적으로 보강했으며, 실패한 경우 검색 결과를 유지했다."
        )
    if report.failed:
        limitations.append("일부 원문 metadata를 확보하지 못해 NAVER 검색 근거만으로 계속 표시했다.")
    if state.warnings:
        limitations.extend(state.warnings)
    if state.status in {RunStatus.NEWS_ONLY, RunStatus.TRENDS_ONLY, RunStatus.PARTIAL}:
        limitations.append("일부 수집 경로가 실패해 성공한 데이터만 게시했다.")

    final_reviews: list[dict[str, object]] = []
    for rank, story in enumerate(stories, 1):
        review = dict(selected_reviews[rank - 1]) if rank <= len(selected_reviews) else {}
        trend_matches = story_trend_matches[rank - 1] if rank <= len(story_trend_matches) else ()
        review.update(
            {
                "rank": rank,
                "headline": story.title,
                "summary": story.summary,
                "topic": story.topic_name,
                "novelty": story.novelty,
                "certainty": story.certainty.value,
                "facts": to_jsonable(story.facts),
                "trend_relationship": story.trend_relationship,
                "trend_matches": [
                    {
                        "group_id": metric.group_id,
                        "group_name": metric.group_name,
                        "topic_id": metric.topic_id,
                        "delta": metric.delta,
                        "state": effective_trend_state(metric),
                        "interpretation": metric.interpretation,
                    }
                    for metric in trend_matches
                ],
                "conflict_state": facts.conflict_state,
                "matched_topic_ids": list(story.matched_topic_ids),
                "why_selected": list(story.why_selected),
                "final_score": story.editorial_score,
            }
        )
        final_reviews.append(review)

    final_funnel = {topic_id: dict(values) for topic_id, values in selection.funnel.items()}
    for topic_id, counts in (retrieval_funnel or {}).items():
        final_funnel.setdefault(topic_id, {}).update(counts)

    return Briefing(
        state=state,
        topics=topics,
        three_line_summary=tuple(lines[:3]),
        stories=tuple(stories),
        news=news,
        trend_metrics=trend_metrics,
        limitations=tuple(dict.fromkeys(limitations)),
        enrichment_attempted=report.attempted,
        enrichment_succeeded=report.succeeded,
        enrichment_failed=report.failed,
        selection_audit=selection.audit,
        selection_funnel=final_funnel,
        selected_reviews=tuple(final_reviews),
        authoritative_audit=authoritative_audit,
        editorial_health=editorial_health,
        strong_rejected_candidates=selection.strong_rejected_candidates,
    )


def make_failure_state(
    *,
    status: RunStatus,
    generated_at: str,
    data_cutoff: str,
    source_mode: str,
    news: CollectorStatus,
    trends: CollectorStatus,
    errors: tuple[str, ...] = (),
) -> RunState:
    return RunState(
        status=status,
        publish=False,
        generated_at=generated_at,
        data_cutoff=data_cutoff,
        source_mode=source_mode,
        news=news,
        trends=trends,
        errors=errors,
    )
