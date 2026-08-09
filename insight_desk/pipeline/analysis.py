from __future__ import annotations

from datetime import datetime

from ..collectors.enrichment import EnrichmentReport
from ..domain.models import (
    Briefing,
    Certainty,
    CollectorStatus,
    EvidenceType,
    NewsItem,
    RunState,
    RunStatus,
    Story,
    Topic,
    TrendMetric,
)
from .clustering import StoryCluster
from .scoring import score_clusters


def _topic_name(topic_id: str, topics: tuple[Topic, ...]) -> str:
    return next((topic.name for topic in topics if topic.id == topic_id), topic_id)


def _trend_for_topic(topic_id: str, metrics: tuple[TrendMetric, ...]) -> tuple[TrendMetric, ...]:
    return tuple(metric for metric in metrics if metric.topic_id == topic_id)


def _trend_sentence(topic_id: str, metrics: tuple[TrendMetric, ...]) -> str:
    relevant = _trend_for_topic(topic_id, metrics)
    if not relevant:
        return "검색어 트렌드 자료가 없어 관심도 변화는 확인할 수 없다."
    rising = [metric.group_name for metric in relevant if metric.delta is not None and metric.delta > 0]
    if rising:
        names = ", ".join(rising[:2])
        return f"{names}에서 뉴스와 같은 기간의 상대 검색지수 상승이 관찰됐지만, 제공 자료만으로 직접 인과관계를 확정할 수 없다."
    if any(metric.interpretation == "비교 기준 부족" for metric in relevant):
        return "관련 검색어의 상대 검색지수는 비교 기준이 부족해 방향을 확정할 수 없다."
    return "관련 검색어의 상대 검색지수에서 같은 방향의 변화는 뚜렷하게 확인되지 않았다."


def _summary_line(cluster: StoryCluster, topic_name: str) -> str:
    representative = cluster.representative
    source_phrase = f"{cluster.source_count}개 출처" if cluster.source_count > 1 else "1개 출처"
    return f"{topic_name}에서 ‘{representative.title}’ 관련 보도가 {source_phrase}에서 확인됐다."


def build_briefing(
    *,
    state: RunState,
    topics: tuple[Topic, ...],
    news: tuple[NewsItem, ...],
    clusters: tuple[StoryCluster, ...],
    trend_metrics: tuple[TrendMetric, ...],
    generated_at: datetime,
    enrichment: EnrichmentReport | None = None,
) -> Briefing:
    topic_by_id = {topic.id: topic for topic in topics}
    ranked_clusters = score_clusters(clusters)
    stories: list[Story] = []
    for cluster in ranked_clusters[:10]:
        representative = cluster.representative
        topic_name = topic_by_id.get(cluster.topic_id, Topic(cluster.topic_id, cluster.topic_id, True, False, 50, ())).name
        summary = representative.summary or "검색 결과에 요약문이 없어 제목과 출처만 확인할 수 있다."
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
        stories.append(
            Story(
                topic_id=cluster.topic_id,
                topic_name=topic_name,
                title=representative.title,
                summary=summary,
                why_it_matters=f"{cluster.source_count}개 출처와 {len(cluster.items)}개 관련 결과가 같은 주제로 묶였다.",
                trend_relationship=_trend_sentence(cluster.topic_id, trend_metrics),
                industry_impact="제공된 제목·검색 요약만으로 구체적인 산업 영향은 확인할 수 없다.",
                investment_relevance="투자 판단에 필요한 재무·공시 자료가 아니므로 투자 영향은 확인하지 않는다.",
                watch_next=("후속 공식 발표와 추가 보도", "다음 브리핑의 상대 검색지수 변화"),
                evidence_ids=tuple(item.evidence_id for item in cluster.items[:4]),
                certainty=Certainty.CONFIRMED,
                score=representative.score,
                source_count=cluster.source_count,
                provenance=provenance,
                metadata_enriched_count=metadata_count,
            )
        )

    lines: list[str] = []
    if stories:
        lines.append(_summary_line(ranked_clusters[0], stories[0].topic_name))
    else:
        lines.append("선택한 관심사에서 표시할 뉴스 결과가 확인되지 않았다.")
    rising = [metric.group_name for metric in trend_metrics if metric.delta is not None and metric.delta > 0]
    if rising:
        lines.append(f"상대 검색지수는 그룹별 직전 구간과 비교했을 때 {', '.join(rising[:2])}에서 상승했다.")
    elif trend_metrics:
        lines.append("검색어 트렌드는 그룹별 직전 구간과 비교해 뚜렷한 상승 신호가 제한적이다.")
    else:
        lines.append("검색어 트렌드 자료는 이번 실행에서 확인되지 않았다.")
    lines.append("뉴스와 검색 관심도의 동시 관찰은 가능하지만, 인과관계는 별도 자료 없이는 확정하지 않는다.")

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
