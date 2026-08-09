from __future__ import annotations

import unittest

from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster, cluster_news
from insight_desk.pipeline.deduplication import deduplicate_news
from insight_desk.pipeline.editorial import assess_cluster, assess_event, assess_relevance
from insight_desk.pipeline.normalization import normalize_news_payloads
from insight_desk.pipeline.novelty import classify_novelty
from insight_desk.pipeline.scoring import score_news
from insight_desk.pipeline.selection import cap_topic_candidates, select_clusters
from insight_desk.pipeline.synthesis import synthesize_cluster


def _topic(
    topic_id: str,
    name: str,
    query: str,
    *,
    anchors: tuple[str, ...] = (),
    negative: tuple[str, ...] = (),
    events: tuple[str, ...] = (),
    required: tuple[str, ...] = (),
    conditional: bool = False,
) -> Topic:
    return Topic(
        topic_id,
        name,
        True,
        conditional,
        50,
        (query,),
        candidate_budget=6,
        intent_anchors=anchors,
        negative_context=negative,
        event_terms=events,
        required_intent_terms=required,
    )


def _item(
    key: str,
    topic_id: str,
    query: str,
    title: str,
    summary: str,
    *,
    domain: str = "example.com",
    metadata_title: str = "",
    metadata_description: str = "",
    official: bool = False,
    score: float = 60.0,
    channels: tuple[str, ...] = (),
) -> NewsItem:
    provenance = (EvidenceType.SEARCH_SNIPPET, EvidenceType.OFFICIAL_SOURCE) if official else (EvidenceType.SEARCH_SNIPPET,)
    if metadata_title or metadata_description:
        provenance = (*provenance, EvidenceType.ENRICHED_METADATA)
    return NewsItem(
        evidence_id=key,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=summary,
        original_url=f"https://{domain}/{key}",
        naver_url="",
        canonical_url=f"https://{domain}/{key}",
        published_at="2026-08-10T07:00:00+09:00",
        source_domain=domain,
        content_hash=key,
        score=score,
        metadata_title=metadata_title,
        metadata_description=metadata_description,
        provenance=provenance,
        matched_topic_ids=(topic_id,),
        retrieval_channels=channels,
    )


class EditorialAcceptanceTests(unittest.TestCase):
    def test_psat_biography_false_positive_is_rejected(self) -> None:
        topic = _topic(
            "psat",
            "PSAT·공채 일정",
            "공무원 시험",
            anchors=("PSAT", "공채", "채용", "시험", "공고"),
            negative=("과거", "거쳐", "보건진료", "가정방문"),
            events=("시험", "채용", "공고", "일정"),
        )
        item = _item("FP-PSAT-01", "psat", "공무원 시험", "진료와 가정방문을 맡은 보건진료소", "2014년 공무원 시험을 거쳐 보건진료소장이 됐다.")
        assessment = assess_cluster(StoryCluster("psat", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_kpop_incidental_idol_reference_is_rejected(self) -> None:
        topic = _topic("kpop", "K-POP", "아이돌", anchors=("K-POP", "앨범", "음원", "차트"), events=("컴백", "앨범", "차트"))
        item = _item("FP-KPOP-01", "kpop", "아이돌", "지역 방송 출연자 인터뷰", "아이돌 게스트가 과거 활동을 회고했다.")
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_hanwha_merchandise_is_not_core_story(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "KBO",
            anchors=("KBO", "프로야구", "한화 이글스", "야구"),
            negative=("굿즈", "유니폼", "패션", "상품"),
            events=("경기", "결과", "부상", "트레이드"),
            conditional=True,
        )
        item = _item("FP-KBO-01", "kbo", "KBO", "KBO 유니폼과 패션 상품 확산", "구단 굿즈와 상품 협업이 늘고 있다.")
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertFalse(assessment.qualified)

    def test_single_source_other_without_concrete_fact_is_rejected(self) -> None:
        topic = _topic("ai", "AI·테크", "AI", anchors=("AI", "인공지능"), events=("발표",))
        item = _item("GENERIC-01", "ai", "AI", "AI 관련 보도", "세부 내용은 추가 확인이 필요하다.")
        assessment = assess_cluster(StoryCluster("ai", (item,)), topic)
        self.assertFalse(assessment.qualified)

    def test_single_official_source_can_pass(self) -> None:
        topic = _topic(
            "psat", "PSAT·공채 일정", "7급 공채", anchors=("7급 공채", "공고"), events=("일정", "공고", "발표")
        )
        item = _item(
            "official-01",
            "psat",
            "7급 공채",
            "2026년 7급 공채 시험 일정 발표",
            "인사혁신처가 원서접수와 시험 일정을 공고했다.",
            domain="www.mpm.go.kr",
            official=True,
        )
        assessment = assess_cluster(StoryCluster("psat", (item,)), topic)
        self.assertTrue(assessment.qualified)

    def test_title_relevance_outweighs_background_match(self) -> None:
        topic = _topic("psat", "PSAT", "공무원 시험", anchors=("공무원 시험", "PSAT"), events=("시험", "공고"))
        direct = _item("direct", "psat", "공무원 시험", "2026년 공무원 시험 일정 공고", "원서접수 일정이 발표됐다.")
        incidental = _item("incidental", "psat", "공무원 시험", "지역 의료 현장 인터뷰", "과거 공무원 시험을 거쳐 일하게 됐다.")
        direct_score = assess_relevance(StoryCluster("psat", (direct,)), topic).score
        incidental_score = assess_relevance(StoryCluster("psat", (incidental,)), topic).score
        self.assertGreater(direct_score, incidental_score)

    def test_named_query_missing_from_title_is_not_saved_by_generic_topic_anchor(self) -> None:
        topic = _topic(
            "ai",
            "AI·테크",
            "Claude",
            anchors=("AI", "인공지능"),
            events=("출시",),
        )
        item = _item(
            "FP-CLAUDE-01",
            "ai",
            "Claude",
            "AI 비용 관리 도구 출시",
            "클로드(Claude) 사용 비용을 줄이는 기능을 공개했다...",
        )
        assessment = assess_cluster(StoryCluster("ai", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_psat_corporate_hiring_without_civil_service_intent_is_rejected(self) -> None:
        topic = _topic(
            "psat",
            "PSAT·공채 일정",
            "채용 일정",
            anchors=("채용", "공고"),
            events=("채용", "공고"),
            required=("PSAT", "5급 공채", "7급 공채", "국가공무원", "공무원 시험"),
            conditional=True,
        )
        item = _item(
            "FP-PSAT-02",
            "psat",
            "채용 일정",
            "근로복지공단 하반기 신입 공개 채용",
            "274명을 채용한다. 지원 자격과 일정은 홈페이지 공고에서 확인할 수 있다.",
        )
        assessment = assess_cluster(StoryCluster("psat", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_generic_kbo_player_story_without_league_or_hanwha_context_is_rejected(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "KBO",
            anchors=("선발", "부상", "경기"),
            events=("선발", "부상"),
            required=("한화", "KBO", "프로야구"),
            conditional=True,
        )
        item = _item(
            "FP-KBO-02",
            "kbo",
            "KBO",
            "100% 회복 안 된 선수, 왜 벌써 선발 투입하나",
            "구단이 선발 투입을 검토하고 있다.",
        )
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_forecast_metric_without_observed_change_is_rejected(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "미국 증시",
            anchors=("미국 증시", "물가", "지표"),
            events=("지표",),
        )
        item = _item(
            "FP-METRIC-01",
            "economy",
            "미국 증시",
            "7월 물가지표에 주목",
            "다음 발표될 지표에 시장의 관심이 쏠린다.",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertFalse(assessment.event.passed)
        self.assertFalse(assessment.qualified)

    def test_number_alone_is_not_an_event(self) -> None:
        topic = _topic("economy", "경제·투자", "환율", anchors=("환율",), events=("환율", "발표"))
        item = _item("number-only", "economy", "환율", "환율 47", "숫자만 제시됐다.")
        self.assertFalse(assess_event(StoryCluster("economy", (item,)), topic).passed)

    def test_metadata_prevents_related_report_fallback(self) -> None:
        topic = _topic("ai", "AI·테크", "AI", anchors=("AI", "로봇"), events=("유치", "출시"))
        item = _item(
            "META-01",
            "ai",
            "AI",
            "잘린 검색 제목...",
            "잘린 검색 설명...",
            metadata_title="아바타 로보틱스, 650만 달러 투자 유치로 사업 확장",
            metadata_description="로봇 기업이 신규 투자를 유치해 사업 확장에 나선다.",
        )
        headline, summary, _, _, _, _ = synthesize_cluster(StoryCluster("ai", (item,)), topic_name=topic.name, trend_metrics=())
        self.assertIn("아바타 로보틱스", headline)
        self.assertNotIn("관련 보도", headline)
        self.assertNotIn("단일 검색 결과만", summary)

    def test_clean_fact_bearing_ellipsis_headline_can_pass(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "한국은행",
            anchors=("한국은행", "환율"),
            events=("통계", "변동폭", "최고"),
        )
        item = _item(
            "ellipsis-fact",
            "economy",
            "한국은행",
            "환율 변동성 금융위기 이후 최고… 월평균 변동 폭 47원",
            "한국은행 통계에 따르면 월평균 환율 변동 폭은 47원으로 집계됐다.",
            domain="publisher.example",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertTrue(assessment.qualified)

    def test_sim_and_date_channels_survive_normalization_and_dedupe(self) -> None:
        payload = {
            "items": [
                {
                    "title": "AI 모델 출시 발표",
                    "description": "새 모델 출시 일정이 발표됐다.",
                    "originallink": "https://example.com/event",
                    "link": "",
                    "pubDate": "Mon, 10 Aug 2026 07:00:00 +0900",
                }
            ]
        }
        normalized = normalize_news_payloads((("ai", "AI", "SIM", payload), ("ai", "AI", "DATE", payload)))
        merged = deduplicate_news(normalized)
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0].retrieval_channels), {"SIM", "DATE"})

    def test_candidate_budget_is_an_actual_merged_cap(self) -> None:
        topic = _topic("ai", "AI", "AI", anchors=("AI",), events=("발표",))
        items = tuple(
            _item(str(index), "ai", "AI", f"AI 발표 {index}", "새 발표 일정이 공개됐다.", score=100 - index)
            for index in range(20)
        )
        bounded = cap_topic_candidates(items, (topic,))
        self.assertLessEqual(len(bounded), topic.candidate_budget)

    def test_event_signature_merges_same_event_but_not_same_entity_different_event(self) -> None:
        topic = _topic("ai", "AI", "AI", anchors=("삼성전자", "AI"), events=("규제", "출시"))
        same_a = _item("same-a", "ai", "AI", "삼성전자 AI 규제 발표", "규제안이 발표됐다.", domain="a.example")
        same_b = _item("same-b", "ai", "AI", "삼성전자 규제 세부안 공개", "같은 규제안의 세부 내용이다.", domain="b.example")
        different = _item("different", "ai", "AI", "삼성전자 신제품 출시", "신제품 출시 일정이 공개됐다.", domain="c.example")
        merged = cluster_news((same_a, same_b, different))
        self.assertTrue(any(len(cluster.items) == 2 for cluster in merged))
        self.assertGreaterEqual(len(merged), 2)

    def test_event_clustering_merges_same_sports_interruption_theme(self) -> None:
        first = _item(
            "heat-a",
            "kbo",
            "프로야구",
            "폭염 뉴노멀 시대 프로야구, 일정 논란",
            "폭염과 경기 일정 부담이 이어지고 있다.",
            domain="a.example",
        )
        second = _item(
            "heat-b",
            "kbo",
            "프로야구",
            "극한 폭염에 멈춘 프로야구",
            "폭염으로 경기가 중단됐다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)

    def test_novelty_states_do_not_fabricate_history(self) -> None:
        self.assertEqual(classify_novelty("MARKET|환율|47원", ()), "UNKNOWN_HISTORY")
        self.assertEqual(classify_novelty("MARKET|환율|47원", ("MARKET|환율|47원",)), "UNCHANGED")
        self.assertEqual(classify_novelty("MARKET|환율|50원", ("MARKET|환율|47원",)), "UPDATE")
        self.assertEqual(classify_novelty("POLICY|PSAT|일정", ("MARKET|환율|47원",)), "NEW")

    def test_story_count_is_variable_and_zero_is_valid(self) -> None:
        topic = _topic("ai", "AI", "AI", anchors=("AI",), events=("발표",))
        strong = _item("one", "ai", "AI", "AI 모델 출시 발표", "새 모델 출시 일정이 공개됐다.")
        result = select_clusters((StoryCluster("ai", (strong,)),), (topic,), limit=10)
        self.assertEqual(len(result.selected), 1)
        weak = _item("weak", "ai", "AI", "AI 관련 보도", "세부 내용은 없다.")
        self.assertEqual(select_clusters((StoryCluster("ai", (weak,)),), (topic,), limit=10).selected, ())


if __name__ == "__main__":
    unittest.main()
