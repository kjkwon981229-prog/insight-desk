from __future__ import annotations

import unittest
from dataclasses import replace

from insight_desk.domain.models import AuthorityEvidence, AuthoritySourceType, EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster, cluster_news
from insight_desk.pipeline.deduplication import deduplicate_news
from insight_desk.pipeline.editorial import assess_cluster, assess_event, assess_relevance, event_signature
from insight_desk.pipeline.normalization import normalize_news_payloads
from insight_desk.pipeline.novelty import classify_novelty
from insight_desk.pipeline.scoring import score_news
from insight_desk.pipeline.selection import cap_topic_candidates, select_clusters
from insight_desk.pipeline.semantics import contains_action, metric_observations, summary_information_gain
from insight_desk.pipeline.synthesis import is_usable_synthesis, synthesize_cluster


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
    def test_disclosure_request_is_policy_not_earnings(self) -> None:
        item = _item(
            "disclosure-request",
            "economy",
            "반도체",
            "거래소, SK하이닉스 충칭공장 지분매각설 조회공시 요구",
            "거래소가 SK하이닉스에 지분매각설에 대한 조회공시를 요구했다.",
        )
        topic = _topic(
            "economy",
            "경제·투자",
            "반도체",
            anchors=("SK하이닉스", "반도체"),
            events=("공시", "요구"),
        )
        cluster = StoryCluster("economy", (item,))
        assessment = assess_event(cluster, topic)
        self.assertEqual(assessment.event_type, "POLICY")
        _, _, _, _, facts, _ = synthesize_cluster(cluster, topic_name="경제·투자", trend_metrics=())
        self.assertEqual(facts.event_type, "POLICY")
    def test_authority_description_cannot_reclassify_discovery_event(self) -> None:
        item = _item(
            "authority-event-type",
            "economy",
            "반도체",
            "소니·TSMC, 日구마모토 이미지 센서 공정에 9조원 합작 투자",
            "소니와 TSMC가 일본 구마모토에서 이미지 센서 공정을 함께 추진한다.",
        )
        item = replace(
            item,
            authoritative_evidence=(
                AuthorityEvidence(
                    adapter="opendart",
                    source_type=AuthoritySourceType.OFFICIAL_CORPORATE,
                    title="소니: 영업실적 공시",
                    description="2026-08-10 금융감독원 공시 접수: 소니 · 영업실적.",
                    publisher="금융감독원 OpenDART",
                    event_key="DART:20260810123456",
                    fact_values=("영업실적", "2026-08-10"),
                ),
            ),
        )
        topic = _topic(
            "economy",
            "경제·투자",
            "반도체",
            anchors=("반도체", "소니", "TSMC"),
            events=("투자", "계약"),
        )
        cluster = StoryCluster("economy", (item,))
        assessment = assess_event(cluster, topic)
        self.assertEqual(assessment.event_type, "INDUSTRY_CHANGE")
        self.assertTrue(assessment.passed)
        _, _, _, _, facts, _ = synthesize_cluster(cluster, topic_name="경제·투자", trend_metrics=())
        self.assertEqual(facts.event_type, assessment.event_type)

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

    def test_kpop_institutional_youth_performance_is_not_core_music_news(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "K-POP",
            anchors=("K-POP", "케이팝", "공연", "앨범", "음원"),
            events=("공연", "앨범", "음원", "컴백"),
        )
        item = _item(
            "FP-KPOP-INSTITUTION-01",
            "kpop",
            "K-POP",
            "경기도교육청, K-POP 댄스 합동 공연 한·일 청소년 협력 폭 확대",
            "교육청이 청소년 국제교류 공연을 열었다.",
            metadata_title="경기도교육청, K-POP 댄스 합동 공연 한·일 청소년 협력 폭 확대",
            metadata_description="한국어 말하기대회 축하공연으로 청소년 교류를 진행했다.",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "LOW_VALUE_APPEARANCE")
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

    def test_abstract_trade_market_is_not_a_roster_event(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "KBO",
            anchors=("KBO", "프로야구", "한화", "야구"),
            events=("경기", "결과", "부상", "트레이드"),
            conditional=True,
        )
        item = _item(
            "FP-KBO-TRADE-MARKET-01",
            "kbo",
            "KBO",
            "얼어붙은 KBO 트레이드 시장",
            "KBO 트레이드 시장 상황이 전해졌다.",
        )
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertEqual(assessment.event.event_type, "OTHER")
        self.assertFalse(assessment.event.passed)
        self.assertFalse(assessment.qualified)

    def test_hanwha_background_player_mention_is_not_core_story(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "프로야구",
            anchors=("KBO", "프로야구", "한화", "야구"),
            negative=("전 프로야구 선수", "전 야구 선수", "결혼", "열애"),
            events=("경기", "결과", "부상", "트레이드"),
            required=("프로야구",),
            conditional=True,
        )
        item = _item(
            "FP-KBO-02",
            "kbo",
            "프로야구",
            "배우 지안, 전 프로야구 선수와 결혼 발표",
            "배우의 결혼 소식에서 전 프로야구 선수 경력이 언급됐다.",
        )
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_hanwha_company_compound_does_not_match_kbo_intent(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "한화 경기",
            anchors=("한화 이글스", "한화 경기", "한화 야구", "KBO", "프로야구", "야구"),
            events=("경기", "결과", "선발", "부상", "트레이드"),
            required=("한화", "한화 이글스", "한화 경기", "KBO", "프로야구"),
            conditional=True,
        )
        item = _item(
            "FP-KBO-COMPANY-01",
            "kbo",
            "한화 경기",
            "코스피, 장중 6320선 상승...코스닥은 바이오·반도체 강세에 3%대 급등",
            "코스피 상승과 한화에어로스페이스 주가 흐름이 함께 언급됐다.",
            metadata_title="코스피, 장중 6320선 상승...코스닥은 바이오·반도체 강세에 3%대 급등",
            metadata_description="코스피가 상승했고 한화에어로스페이스가 관련 종목으로 언급됐다.",
        )
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertFalse(assessment.relevance.passed)
        self.assertFalse(assessment.qualified)

    def test_single_source_other_without_concrete_fact_is_rejected(self) -> None:
        topic = _topic("ai", "AI·테크", "AI", anchors=("AI", "인공지능"), events=("발표",))
        item = _item("GENERIC-01", "ai", "AI", "AI 관련 보도", "세부 내용은 추가 확인이 필요하다.")
        assessment = assess_cluster(StoryCluster("ai", (item,)), topic)
        self.assertFalse(assessment.qualified)

    def test_truncated_single_source_metric_without_trusted_lead_is_rejected(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "한국은행",
            anchors=("한국은행", "환율", "원·달러"),
            events=("변동성", "최고", "환율"),
        )
        item = _item(
            "single-source-metric-fallback",
            "economy",
            "한국은행",
            "원·달러 환율 스터 변동성···금융위기 이후 최고",
            "원·달러 환율의 1300원 수치가 한 건의 보도에서 제시됐다...",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic, novelty="NEW")
        self.assertIn(assessment.event.event_type, {"STATISTIC", "MARKET_MOVE"})
        self.assertIn("SINGLE_SOURCE_METRIC_WITHOUT_TRUSTED_LEAD", assessment.reasons)
        self.assertFalse(assessment.qualified)

    def test_complete_single_source_metric_remains_eligible(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "물가",
            anchors=("물가", "소비자물가"),
            events=("상승", "지표"),
        )
        item = _item(
            "single-source-metric-complete",
            "economy",
            "물가",
            "6월 소비자물가 2.7% 상승",
            "통계청에 따르면 6월 소비자물가는 전년 동월보다 2.7% 상승했다.",
            metadata_title="6월 소비자물가 2.7% 상승",
            metadata_description="통계청에 따르면 6월 소비자물가는 전년 동월보다 2.7% 상승했다.",
            score=72.0,
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "STATISTIC")
        self.assertTrue(assessment.qualified)

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

    def test_vague_weekly_schedule_title_is_not_a_concrete_event(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "한국은행",
            anchors=("한국은행", "금융당국"),
            events=("일정",),
        )
        item = _item(
            "vague-schedule",
            "economy",
            "한국은행",
            "금주 한국은행 및 금융당국 주요일정",
            "",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertEqual(assessment.event.event_type, "ROUTINE_SCHEDULE")
        self.assertFalse(assessment.qualified)

    def test_dated_weekly_schedule_roundup_is_not_a_core_event(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "한국은행",
            anchors=("한국은행", "금융당국"),
            events=("일정", "개최"),
        )
        item = _item(
            "routine-schedule",
            "economy",
            "한국은행",
            "금주 한국은행 및 금융당국 주요일정 8월10일 개최",
            "금융당국의 이번 주 일정을 정리했다.",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertEqual(assessment.event.event_type, "ROUTINE_SCHEDULE")
        self.assertFalse(assessment.event.passed)
        self.assertFalse(assessment.qualified)

    def test_truncated_analysis_headline_without_safe_lead_is_not_a_schedule(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "SM",
            anchors=("SM", "공연", "음반", "가수"),
            events=("공연", "매출", "실적"),
        )
        item = _item(
            "truncated-earnings-headline",
            "kpop",
            "SM",
            "음반보다 공연이 효자… SM, 매출 3496억·영업익 529억",
            "SM 엔터테인먼트가 올해 2분기 실적 성장을 기록했다고 밝혔다...",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "SCHEDULED_EVENT")
        self.assertIn("TRUNCATED_EVENT_WITHOUT_LEAD", assessment.reasons)
        self.assertFalse(assessment.qualified)

    def test_completed_comeback_uses_the_same_event_type_as_synthesis(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "JYP",
            anchors=("가수", "컴백", "그룹"),
            events=("컴백", "공연"),
        )
        item = _item(
            "completed-comeback-event",
            "kpop",
            "박진영",
            "박진영, 6년만 여름 컴백 SWEAT 활동 성료",
            "박진영의 컴백 활동이 성료됐다.",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "ENTERTAINMENT_EVENT")
        self.assertTrue(assessment.event.passed)
        self.assertTrue(assessment.qualified)

    def test_new_song_announcement_uses_product_release_event_type(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "빅뱅",
            anchors=("빅뱅", "그룹", "신곡", "앨범"),
            events=("발표", "신곡", "앨범"),
        )
        item = _item(
            "bigbang-new-song",
            "kpop",
            "빅뱅",
            "데뷔 20주년 빅뱅, 완전체로 신곡 빅(BiiiG) 발표",
            "빅뱅이 신곡을 발표했다.",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "PRODUCT_RELEASE")
        self.assertTrue(assessment.event.passed)
        self.assertTrue(assessment.qualified)

    def test_run76_market_observations_keep_instrument_value_and_direction_bound(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "코스닥",
            anchors=("코스닥", "코스피"),
            events=("상승", "급등"),
        )
        item = _item(
            "run76-market-binding",
            "economy",
            "코스닥",
            "코스닥 +6.97% 급등, 코스피 +0.65% 소폭 상승",
            "코스닥은 6.97% 급등했고 코스피는 0.65% 소폭 상승했다.",
            metadata_title="코스닥 +6.97% 급등, 코스피 +0.65% 소폭 상승",
            metadata_description="코스닥은 6.97% 급등했고 코스피는 0.65% 소폭 상승했다.",
            score=90.0,
        )
        observations = metric_observations(item.title)
        self.assertEqual([(value.instrument, value.value) for value in observations], [("코스닥", "+6.97%"), ("코스피", "+0.65%")])
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic, novelty="NEW")
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("economy", (item,)),
            topic_name=topic.name,
            trend_metrics=(),
            event_type_override=assessment.event.event_type,
            event_signature_override=assessment.event_signature,
        )
        self.assertIn("코스닥", summary)
        self.assertIn("6.97%", summary)
        self.assertIn("코스피", summary)
        self.assertIn("0.65%", summary)
        self.assertEqual(facts.subject, "코스닥")
        self.assertEqual(facts.key_numbers[:2], ("+6.97%", "+0.65%"))
        self.assertNotIn("코스피는 0.65%로 급등했다", summary)

    def test_run76_korean_action_boundaries_reject_collision_substrings(self) -> None:
        self.assertFalse(contains_action("음악 보부상 스트레이 키즈", "부상"))
        self.assertFalse(contains_action("NH투자증권", "투자"))
        self.assertFalse(contains_action("장기투자 하라더니", "투자"))
        self.assertTrue(contains_action("선수 부상으로 경기 중단", "부상"))

    def test_run76_query_only_ai_match_is_rejected_but_real_model_release_survives(self) -> None:
        topic = _topic("ai_tech", "AI·테크", "ChatGPT", anchors=("AI", "ChatGPT", "모델"), events=("발표", "공개"))
        incidental = _item(
            "run76-ai-incidental",
            "ai_tech",
            "ChatGPT",
            "AI·투자교육·실전투자 삼박자",
            "AI를 활용한 투자교육과 실전투자 전략을 소개했다.",
        )
        self.assertFalse(assess_cluster(StoryCluster("ai_tech", (incidental,)), topic, novelty="NEW").qualified)
        actual = _item(
            "real-chatgpt-release",
            "ai_tech",
            "OpenAI",
            "OpenAI, 새 ChatGPT 모델 공개",
            "OpenAI가 8월 10일 새 모델을 공개했다.",
            metadata_title="OpenAI, 새 ChatGPT 모델 공개",
            metadata_description="OpenAI가 8월 10일 새 모델을 공개했다.",
            score=90.0,
        )
        self.assertTrue(assess_cluster(StoryCluster("ai_tech", (actual,)), replace(topic, news_queries=("OpenAI",)), novelty="NEW").qualified)

    def test_run76_event_date_conflict_rejects_candidate(self) -> None:
        topic = _topic("kpop", "K-POP", "빅뱅", anchors=("빅뱅", "신곡"), events=("발표",))
        item = _item(
            "date-conflict",
            "kpop",
            "빅뱅",
            "빅뱅 19일 신곡 발표",
            "빅뱅의 20일 신곡 발표가 예정됐다.",
            metadata_title="빅뱅 19일 신곡 발표",
            metadata_description="빅뱅의 20일 신곡 발표가 예정됐다.",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertFalse(assessment.event.passed)
        self.assertIn("EVENT_DATE_CONFLICT", assessment.event.reasons)

    def test_run76_summary_information_gain_and_generic_evidence_macro_are_gated(self) -> None:
        self.assertFalse(summary_information_gain("AI 모델 출시 발표", "AI 모델 출시 발표."))
        self.assertFalse(is_usable_synthesis(
            "AI 모델 출시 발표",
            "여러 매체에서 같은 핵심 내용이 확인됐다.",
            source_count=2,
        ))

    def test_run76_incidental_ai_candidate_does_not_fill_a_slot(self) -> None:
        topic = _topic("ai_tech", "AI·테크", "ChatGPT", anchors=("AI", "ChatGPT"), events=("투자",))
        item = _item(
            "run76-nh-investment",
            "ai_tech",
            "ChatGPT",
            "NH투자증권, AI 기반 투자 전략 구현 지원",
            "NH투자증권이 투자 전략 구현을 지원한다고 전했다.",
        )
        result = select_clusters((StoryCluster("ai_tech", (item,)),), (topic,), limit=10)
        self.assertEqual(result.selected, ())

    def test_secondary_release_word_does_not_change_primary_announcement_type(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "JYP",
            anchors=("JYP", "그룹", "데뷔"),
            events=("발표", "공개", "데뷔"),
        )
        primary = _item(
            "primary-announcement",
            "kpop",
            "JYP",
            "JYP 신인 걸그룹 아워벌스데이, 데뷔 콘셉트 포토 공개",
            "JYP가 데뷔 콘셉트 포토를 공개했다.",
            score=70.0,
        )
        secondary = _item(
            "secondary-release",
            "kpop",
            "JYP",
            "JYP 아워벌스데이 데뷔곡 발표",
            "아워벌스데이 데뷔곡 발표 소식이다.",
            score=40.0,
        )
        assessment = assess_cluster(StoryCluster("kpop", (primary, secondary)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "ANNOUNCEMENT")

    def test_concrete_recruitment_result_uses_personnel_event_type(self) -> None:
        topic = _topic(
            "psat",
            "PSAT·공채 일정",
            "7급 공채",
            anchors=("7급 공채", "공무원", "선발"),
            events=("공채", "선발", "시험"),
            required=("7급 공채",),
            conditional=True,
        )
        item = _item(
            "recruitment-result",
            "psat",
            "7급 공채",
            "부산시, 올 지방공무원 7급 공채 71.5대 1",
            "부산시 지방공무원 7급 공채에서 38명 선발에 1,461명이 지원했다.",
            metadata_title="부산시, 올 지방공무원 7급 공채 71.5대 1",
            metadata_description="부산시 지방공무원 7급 공채에서 38명 선발에 1,461명이 지원했다.",
        )
        assessment = assess_cluster(StoryCluster("psat", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "RECRUITMENT_COMPETITION")
        self.assertTrue(assessment.event.passed)
        self.assertTrue(assessment.qualified)

    def test_primary_etf_release_is_not_retyped_from_secondary_lead_context(self) -> None:
        topic = _topic(
            "ai",
            "AI·테크",
            "반도체",
            anchors=("반도체", "ETF"),
            events=("출시", "상장"),
        )
        primary = _item(
            "etf-release",
            "ai",
            "반도체",
            "반도체·조선·방산·원자력 하나로 묶은 ETF 출격",
            "오는 11일 반도체 관련 신규 ETF가 출시된다.",
            metadata_title="반도체·조선·방산·원자력 하나로 묶은 ETF 출격",
            metadata_description="오는 11일 반도체 관련 신규 ETF가 출시된다.",
        )
        secondary = _item(
            "etf-secondary-context",
            "ai",
            "반도체",
            "반도체 ETF 투자 규제와 시장 전망",
            "시장 규제와 제도 변화가 논의됐다.",
            score=30.0,
        )
        assessment = assess_cluster(StoryCluster("ai", (primary, secondary)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "PRODUCT_RELEASE")

    def test_fan_invitation_background_is_not_misclassified_from_historical_lead(self) -> None:
        topic = _topic(
            "kpop",
            "엔터·음악·K-POP",
            "YG",
            anchors=("YG", "블랙핑크", "공연", "앨범"),
            events=("공연", "앨범", "차트", "매출"),
        )
        item = _item(
            "blackpink-fan-invite",
            "kpop",
            "YG",
            "블랙핑크 10주년 행사, 팬 40명 부르더니…답례품은 6900원짜리 떡?",
            "2022년 정규 2집으로 빌보드 앨범 차트를 석권했고 2023년에는 YG와 전속계약을 체결했다.",
        )
        assessment = assess_cluster(StoryCluster("kpop", (item,)), topic, novelty="NEW")
        self.assertEqual(assessment.event.event_type, "LOW_VALUE_APPEARANCE")
        self.assertFalse(assessment.qualified)

    def test_event_signature_does_not_use_metadata_tail_numbers(self) -> None:
        topic = _topic("economy", "경제·투자", "코스피", anchors=("코스피",), events=("상승",))
        item = _item(
            "market-tail-signature",
            "economy",
            "코스피",
            "코스피 0.76% 상승 출발",
            "코스피가 상승 출발했다.",
            metadata_description="10일 코스피가 상승했고 7일 수치는 47.56포인트였다.",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic, novelty="NEW")
        self.assertNotIn("10일", assessment.event_signature)
        self.assertNotIn("47.56", assessment.event_signature)

    def test_event_signature_uses_the_same_headline_evidence_as_synthesis(self) -> None:
        topic = _topic("economy", "경제·투자", "코스피", anchors=("코스피",), events=("상승",))
        cluster = StoryCluster(
            "economy",
            (
                _item(
                    "market-analysis-title",
                    "economy",
                    "코스피",
                    "반도체 투톱 상승에… 코스피 장 초반 6300선 회복",
                    "코스피가 상승 출발했다.",
                    score=90.0,
                ),
                _item(
                    "market-core-title",
                    "economy",
                    "코스피",
                    "코스피 0.76%·코스닥 1.11% 상승 출발",
                    "코스피와 코스닥이 상승 출발했다.",
                    score=60.0,
                ),
            ),
        )
        assessment = assess_cluster(cluster, topic, novelty="NEW")
        self.assertIn("0.76%", assessment.event_signature)
        self.assertNotIn("반도체", assessment.event_signature)

    def test_ceremonial_first_pitch_is_not_core_sports_news(self) -> None:
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "프로야구",
            anchors=("KBO", "프로야구", "한화", "야구"),
            events=("일정", "시구"),
            required=("프로야구",),
            conditional=True,
        )
        item = _item(
            "routine-first-pitch",
            "kbo",
            "프로야구",
            "가수 민니, 11일 두산-한화전 시구",
            "잠실 경기에서 시구에 나선다.",
        )
        assessment = assess_cluster(StoryCluster("kbo", (item,)), topic)
        self.assertEqual(assessment.event.event_type, "LOW_VALUE_APPEARANCE")
        self.assertFalse(assessment.event.passed)
        self.assertFalse(assessment.qualified)

    def test_routine_ndf_quote_is_not_core_market_event(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "원달러 환율",
            anchors=("원달러 환율", "환율"),
            events=("하락", "환율"),
        )
        item = _item(
            "routine-ndf",
            "economy",
            "원달러 환율",
            "원·달러 NDF 1407.2/1407.6원, 8.15원 하락",
            "NDF 환율이 하락했다.",
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertEqual(assessment.event.event_type, "ROUTINE_MARKET_QUOTE")
        self.assertFalse(assessment.event.passed)
        self.assertFalse(assessment.qualified)

    def test_different_dated_artist_releases_do_not_merge(self) -> None:
        first = _item(
            "release-a",
            "kpop",
            "K-POP",
            "에반, 9월 7일 미니 1집 발매",
            "에반의 새 앨범 발매 일정이 공개됐다.",
            domain="a.example",
        )
        second = _item(
            "release-b",
            "kpop",
            "K-POP",
            "몬스타엑스, 9월 4일 미니 앨범 컴백",
            "몬스타엑스가 9월 컴백한다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 2)

    def test_policy_aliases_merge_same_directive_across_company_shorthand(self) -> None:
        first = _item(
            "directive-full-company",
            "ai_tech",
            "반도체",
            "추미애 삼성·SK하이닉스, 반도체 폐수 방류 줄여라",
            "반도체 기업에 방류량 저감을 요구했다.",
            domain="a.example",
        )
        second = _item(
            "directive-short-company",
            "ai_tech",
            "반도체",
            "추미애 삼전·닉스 반도체 공정수 방류 최소화 재차 요구",
            "삼성전자와 SK하이닉스에 공정수 방류 최소화를 요구했다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)

    def test_same_dated_artist_release_headlines_still_merge(self) -> None:
        first = _item(
            "same-release-a",
            "kpop",
            "K-POP",
            "에반, 9월 7일 미니 1집 발매",
            "에반의 새 앨범 발매 일정이 공개됐다.",
            domain="a.example",
        )
        second = _item(
            "same-release-b",
            "kpop",
            "K-POP",
            "에반 9월 7일 컴백 일정 공개",
            "에반의 9월 7일 컴백 소식이 전해졌다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].items), 2)

    def test_same_date_different_artist_releases_do_not_merge(self) -> None:
        first = _item(
            "same-day-release-a",
            "kpop",
            "가요계",
            "클유아, 9월 말 컴백 확정…신보 발매",
            "클로즈 유어 아이즈가 9월 말 컴백한다.",
            domain="a.example",
        )
        second = _item(
            "same-day-release-b",
            "kpop",
            "가요계",
            "몬스타엑스, 9월 가요계 컴백 확정…앨범 발매",
            "몬스타엑스가 9월 4일 미니 앨범을 발매한다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 2)

    def test_metadata_tail_does_not_merge_yg_analysis_into_bigbang_release(self) -> None:
        release = _item(
            "bigbang-release",
            "kpop",
            "YG",
            "빅뱅, 19일 데뷔 20주년 기념 BiiG 발매",
            "빅뱅이 19일 신곡을 발표한다.",
            domain="release.example",
        )
        analyst = _item(
            "yg-analysis",
            "kpop",
            "YG",
            "6년 만의 신인 보이그룹, YG냐 SM이냐",
            "YG의 라인업과 실적을 분석했다.",
            metadata_description="빅뱅 20주년 월드투어도 예정됐다고 덧붙였다.",
            domain="analyst.example",
        )
        clusters = cluster_news((release, analyst))
        self.assertEqual(len(clusters), 2)

    def test_same_artist_release_and_anniversary_project_do_not_merge(self) -> None:
        release = _item(
            "bigbang-release-event",
            "kpop",
            "YG",
            "빅뱅, 19일 데뷔 20주년 기념 BiiG 발매",
            "빅뱅이 19일 신곡을 발표한다.",
            domain="release.example",
        )
        project = _item(
            "bigbang-project-event",
            "kpop",
            "YG",
            "롯데백화점, YG와 협업…빅뱅 데뷔 20주년 기념 프로젝트",
            "롯데백화점이 빅뱅 20주년 기념 전시 프로젝트를 추진한다.",
            domain="project.example",
        )
        clusters = cluster_news((release, project))
        self.assertEqual(len(clusters), 2)

    def test_anniversary_context_does_not_bridge_a_release_cluster(self) -> None:
        release = _item(
            "bigbang-release-bridge",
            "kpop",
            "YG",
            "빅뱅, 19일 데뷔 20주년 기념 BiiG 발매",
            "빅뱅이 19일 신곡을 발표한다.",
            domain="release.example",
        )
        anniversary = _item(
            "bigbang-anniversary-bridge",
            "kpop",
            "아이돌",
            "글로벌 아이돌의 시작, 빅뱅 20주년에…잠실도 들썩",
            "롯데백화점이 빅뱅 20주년 기념 프로젝트를 추진한다.",
            domain="anniversary.example",
        )
        project = _item(
            "bigbang-project-bridge",
            "kpop",
            "K-POP",
            "롯데백화점, YG와 빅뱅 20주년 기념 프로젝트",
            "롯데백화점이 빅뱅 20주년 기념 전시 프로젝트를 추진한다.",
            domain="project.example",
        )
        clusters = cluster_news((release, anniversary, project))
        release_cluster = next(cluster for cluster in clusters if release in cluster.items)
        self.assertEqual([item.evidence_id for item in release_cluster.items], [release.evidence_id])

    def test_date_only_breaking_event_can_pass(self) -> None:
        topic = _topic(
            "economy",
            "경제·투자",
            "한국은행",
            anchors=("한국은행", "기준금리"),
            events=("기준금리", "발표"),
        )
        item = _item(
            "date-only-event",
            "economy",
            "한국은행",
            "한국은행, 8월 14일 기준금리 발표",
            "기준금리 결정 결과를 발표한다.",
            channels=("DATE",),
        )
        assessment = assess_cluster(StoryCluster("economy", (item,)), topic)
        self.assertTrue(assessment.qualified)

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

    def test_same_semiconductor_theme_does_not_merge_different_events(self) -> None:
        hbf = _item(
            "hbf-event",
            "ai",
            "반도체",
            "한미반도체, HBF 상용화 임박 수혜",
            "한미반도체의 HBF 상용화와 TC 본더 수율 검증이 전해졌다.",
            metadata_title="한미반도체, HBF 상용화 임박 수혜",
            metadata_description="비메모리 첨단 패키징 투자 확대가 예상된다.",
            domain="hbf.example",
        )
        china = _item(
            "china-market",
            "economy",
            "물가",
            "10일 중국증시 첨단산업 모멘텀",
            "중국증시와 물가 흐름을 정리했다.",
            domain="china.example",
        )
        morgan = _item(
            "morgan-market",
            "ai",
            "반도체",
            "모건스탠리 메모리 반도체주 조정 끝",
            "메모리 반도체주의 조정이 끝났다고 분석했다.",
            metadata_title="모건스탠리 메모리 반도체주 조정 끝",
            metadata_description="최근 주가 급락과 투자 재진입 기회를 분석했다.",
            domain="morgan.example",
        )
        clusters = cluster_news((hbf, china, morgan))
        self.assertEqual(len(clusters), 3)

    def test_generic_support_term_does_not_merge_unrelated_psat_event(self) -> None:
        incidental = replace(
            _item(
                "psat-incidental-support",
                "psat",
                "공무원 시험",
                "한경협, 창업팀 100개 선발·투자 연계 지원 나선다",
                "창업팀 지원과 투자 연계 프로그램을 소개했다.",
            ),
            matched_topic_ids=("psat",),
        )
        real = replace(
            _item(
                "psat-real-recruitment",
                "psat",
                "PSAT",
                "서울시, 올 지방공무원 7급 공채 272명 선발에 11,187명 지원",
                "서울시 지방공무원 7급 공채와 PSAT 대체 방식을 안내했다.",
            ),
            matched_topic_ids=("psat",),
        )
        clusters = cluster_news((incidental, real))
        psat_clusters = [cluster for cluster in clusters if cluster.topic_id == "psat"]
        self.assertEqual(len(psat_clusters), 2)
        self.assertTrue(all(len(cluster.items) == 1 for cluster in psat_clusters))

    def test_market_instruments_do_not_merge_through_shared_rate_context(self) -> None:
        stock = _item(
            "market-stock-context",
            "economy",
            "기준금리",
            "[특징주]SK하이닉스·삼성전자 나란히 상승…낙폭과대·금리 인하 기대",
            "금리 인하 기대가 반도체주 상승 배경으로 거론됐다.",
        )
        currency = _item(
            "market-yen-context",
            "economy",
            "기준금리",
            "엔화, 美 조기 금리 인상 관측 후퇴에 1달러=157엔대 후반 상승 출발",
            "엔화가 금리 전망 변화로 상승 출발했다.",
        )
        clusters = cluster_news((stock, currency))
        self.assertEqual(len(clusters), 2)
        self.assertTrue(all(len(cluster.items) == 1 for cluster in clusters))

    def test_secondary_market_clause_does_not_bridge_index_and_currency_events(self) -> None:
        index = _item(
            "market-index-event",
            "economy",
            "코스피",
            "코스피 6300선 상승 출발",
            "코스피가 6300선에서 상승 출발했다.",
        )
        overview = _item(
            "market-overview-event",
            "economy",
            "코스피",
            "[위클리오늘] 코스피 6300선 상승 출발···환율 1410원대",
            "코스피는 6300선을 회복했고 환율은 1410원대였다.",
        )
        currency = _item(
            "market-currency-event",
            "economy",
            "원달러 환율",
            "원·달러 환율 1410원대 등락",
            "원·달러 환율이 1410원대에서 등락했다.",
        )
        clusters = cluster_news((index, overview, currency))
        self.assertEqual(len(clusters), 2)
        index_cluster = next(
            cluster
            for cluster in clusters
            if {item.evidence_id for item in cluster.items} == {"market-index-event", "market-overview-event"}
        )
        self.assertNotIn("환율", event_signature(index_cluster))
        self.assertTrue(any({item.evidence_id for item in cluster.items} == {"market-currency-event"} for cluster in clusters))

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

    def test_heat_exception_does_not_use_snippet_tail_to_merge_first_pitch(self) -> None:
        heat = _item(
            "heat-tail",
            "kbo",
            "프로야구",
            "프로야구 폭염으로 경기 중단",
            "폭염으로 리그 일정이 중단됐다.",
            domain="heat.example",
        )
        first_pitch = _item(
            "pitch-tail",
            "kbo",
            "프로야구",
            "아이들 민니, 11일 잠실 두산-한화전 시구",
            "폭염으로 중단된 경기가 재개되며 시구자로 나선다.",
            domain="pitch.example",
        )
        clusters = cluster_news((heat, first_pitch))
        self.assertEqual(len(clusters), 2)

    def test_same_date_does_not_merge_heat_interruption_and_first_pitch(self) -> None:
        heat = _item(
            "live-heat",
            "kbo",
            "KBO",
            "'폭염 방학' 뒤 55경기 재편… KBO, 11일부터 후반기 재출발",
            "KBO 리그가 폭염 중단을 마치고 11일부터 일정을 다시 소화한다.",
            domain="heat.example",
        )
        first_pitch = _item(
            "live-first-pitch",
            "kbo",
            "한화 경기",
            "아이들 민니, 프로야구 11일 잠실 두산-한화전 시구",
            "두산 베어스가 한화 이글스와의 홈 경기 시구자를 선정했다.",
            domain="pitch.example",
        )
        clusters = cluster_news((heat, first_pitch))
        self.assertEqual(len(clusters), 2)

    def test_heat_tail_player_analysis_does_not_merge_with_interruption(self) -> None:
        heat = _item(
            "live-heat-event",
            "kbo",
            "KBO",
            "프로야구 폭염으로 경기 중단",
            "폭염으로 리그 일정이 중단됐다.",
            domain="heat.example",
        )
        player = _item(
            "live-player-tail",
            "kbo",
            "KBO",
            "\"관심 가진 구단들 많더라\" 예비 FA 호령존 쟁탈전 벌어지나...폭염 재정...",
            "KBO 리그 중견수의 FA 가치와 쟁탈전을 분석했다.",
            domain="player.example",
        )
        clusters = cluster_news((heat, player))
        self.assertEqual(len(clusters), 2)

    def test_shared_market_level_does_not_merge_level_and_volatility_events(self) -> None:
        level = _item(
            "live-level",
            "economy",
            "원달러 환율",
            "안정 찾는 외환시장… 원·달러 1300원대 초읽기",
            "원·달러 환율 수준과 함께 변동성이 점차 안정화됐다.",
            domain="level.example",
        )
        volatility = _item(
            "live-volatility",
            "economy",
            "원달러 환율",
            "이젠 1300원대 환율? 변동폭 금융위기 이후 최대",
            "올해 환율 변동성이 글로벌 금융위기 이후 가장 큰 것으로 나타났다.",
            domain="volatility.example",
        )
        clusters = cluster_news((level, volatility))
        self.assertEqual(len(clusters), 2)

    def test_sports_interruption_preserves_headline_action(self) -> None:
        item = _item(
            "heat-action",
            "kbo",
            "KBO",
            "프로야구 폭염으로 경기 중단",
            "폭염으로 리그 일정이 중단됐다.",
        )
        _, _, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kbo", (item,)), topic_name="KBO·한화 이글스", trend_metrics=()
        )
        self.assertEqual(facts.subject, "프로야구")
        self.assertEqual(facts.action, "중단")

    def test_sports_interruption_uses_trusted_metadata_date(self) -> None:
        item = _item(
            "heat-metadata-date",
            "kbo",
            "KBO",
            "'폭염 휴식' 마친 KBO리그 11일 재개...",
            "검색 결과가 잘렸다...",
            metadata_title="'폭염 휴식' 마친 KBO리그 11일 재개...",
            metadata_description="폭염으로 일시 중단됐던 KBO리그가 오는 11일 다시 시작한다.",
        )
        _, _, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kbo", (item,)), topic_name="KBO·한화 이글스", trend_metrics=()
        )
        self.assertEqual(facts.date, "11일")

    def test_heat_analysis_headline_merges_into_interruption_event(self) -> None:
        first = _item(
            "heat-analysis",
            "kbo",
            "한화 야구",
            "39~40도 폭염은 지났다→체력 충전+선발진 리셋",
            "한국 야구 위원회(KBO)가 폭염 취소 규정을 세분화했다.",
            domain="a.example",
        )
        second = _item(
            "heat-event",
            "kbo",
            "KBO",
            "극한 폭염에 멈춘 프로야구",
            "기록적인 폭염으로 프로야구가 닷새 동안 멈춰섰다.",
            domain="b.example",
        )
        topic = _topic(
            "kbo",
            "KBO·한화 이글스",
            "KBO",
            anchors=("KBO", "프로야구", "한화", "야구"),
            events=("경기", "폭염", "중단"),
            required=("KBO",),
            conditional=True,
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 1)
        assessment = assess_event(clusters[0], topic)
        self.assertEqual(assessment.event_type, "SPORTS_INTERRUPTION")
        self.assertTrue(assessment.passed)

    def test_chart_summary_keeps_first_place_fact(self) -> None:
        item = _item(
            "chart-fact",
            "kpop",
            "음악 차트",
            "스트레이 키즈, THIS & THAT 국내외 음악 차트 1위",
            "컴백 당일 음악 방송 활동에 돌입했다.",
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kpop", (item,)), topic_name="K-POP", trend_metrics=()
        )
        self.assertIn("1위", headline)
        self.assertIn("1위", summary)
        self.assertEqual(facts.event_type, "AWARD_CHART")

    def test_market_summary_keeps_supported_volatility_change(self) -> None:
        item = _item(
            "market-fact",
            "economy",
            "원달러 환율",
            "이젠 1300원대 환율? 변동폭 금융위기 이후 최대",
            "",
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("economy", (item,)), topic_name="경제·투자", trend_metrics=()
        )
        self.assertIn("변동성", summary)
        self.assertIn("금융위기 이후 최대", summary)
        self.assertNotIn("1300원으로", summary)
        self.assertEqual(facts.event_type, "MARKET")

    def test_market_level_is_not_reported_as_volatility_size(self) -> None:
        item = _item(
            "market-level",
            "economy",
            "원달러 환율",
            "안정 찾는 외환시장 원·달러 1300원대 환율, 변동성 금융위기 이후 최대",
            "원·달러 환율 수준이 1300원대에 접근하는 가운데 올해 변동성이 금융위기 이후 가장 큰 것으로 나타났다.",
        )
        _, summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("economy", (item,)), topic_name="경제·투자", trend_metrics=()
        )
        self.assertIn("변동성이", summary)
        self.assertNotIn("1300원으로", summary)

    def test_market_level_is_not_replaced_by_secondary_market_change(self) -> None:
        item = _item(
            "kospi-level-secondary-change",
            "economy",
            "미국 증시",
            "코스피 기관 매수세에 장중 6300선 강보합세, 코스닥 4%대 오른 830선",
            "코스피가 6300선에서 강보합세를 보였고 코스닥은 4%대 올랐다.",
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("economy", (item,)), topic_name="경제·투자", trend_metrics=()
        )
        self.assertIn("6300선", headline)
        self.assertNotEqual(facts.key_numbers[0], "4%")
        self.assertIn("강보합세", summary)

    def test_snippet_tail_does_not_merge_unrelated_events(self) -> None:
        first = _item(
            "cluster-tail-a",
            "kpop",
            "JYP",
            "스트레이 키즈 리믹스 공개",
            "JYP가 새 공연을 준비하는 가운데 관련 일정이 공개됐다.",
            domain="a.example",
        )
        second = _item(
            "cluster-tail-b",
            "kpop",
            "SM",
            "SM 2분기 실적 발표",
            "SM 실적 발표와 함께 JYP 공연 관련 내용도 언급됐다.",
            domain="b.example",
        )
        clusters = cluster_news((first, second))
        self.assertEqual(len(clusters), 2)

    def test_novelty_states_do_not_fabricate_history(self) -> None:
        self.assertEqual(classify_novelty("MARKET|환율|47원", ()), "UNKNOWN_HISTORY")
        self.assertEqual(classify_novelty("MARKET|환율|47원", ("MARKET|환율|47원",)), "UNCHANGED")
        self.assertEqual(classify_novelty("MARKET|환율|50원", ("MARKET|환율|47원",)), "UPDATE")
        self.assertEqual(classify_novelty("POLICY|PSAT|일정", ("MARKET|환율|47원",)), "NEW")

    def test_story_count_is_variable_and_zero_is_valid(self) -> None:
        topic = _topic("ai", "AI", "AI", anchors=("AI",), events=("발표",))
        strong = _item("one", "ai", "AI", "AI 모델 출시 발표", "8월 10일 새 모델 출시 일정이 공개됐다.")
        result = select_clusters((StoryCluster("ai", (strong,)),), (topic,), limit=10)
        self.assertEqual(len(result.selected), 1)
        weak = _item("weak", "ai", "AI", "AI 관련 보도", "세부 내용은 없다.")
        self.assertEqual(select_clusters((StoryCluster("ai", (weak,)),), (topic,), limit=10).selected, ())


if __name__ == "__main__":
    unittest.main()
