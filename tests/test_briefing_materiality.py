from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster
from insight_desk.pipeline.selection import select_clusters


TOPICS, _ = load_topics(Path("config/topics.json"))
TOPIC = {topic.id: topic for topic in TOPICS}


def item(key: str, topic_id: str, query: str, title: str, summary: str) -> NewsItem:
    return NewsItem(
        evidence_id=key,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=summary,
        original_url=f"https://fixture.test/{key}",
        naver_url="",
        canonical_url=f"https://fixture.test/{key}",
        published_at="2026-08-21T10:00:00+09:00",
        source_domain="fixture.test",
        content_hash=key,
        score=90.0,
        metadata_title=title,
        metadata_description=summary,
        metadata_canonical_url=f"https://fixture.test/{key}",
        publisher="Fixture News",
        metadata_published_at="2026-08-21T10:00:00+09:00",
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class BriefingMaterialityTests(unittest.TestCase):
    def assessment(self, key: str, topic_id: str, query: str, title: str, summary: str):
        story = item(key, topic_id, query, title, summary)
        return assess_cluster(StoryCluster(topic_id, (story,)), TOPIC[topic_id], novelty="NEW")

    def test_soft_promo_and_lifestyle_content_is_not_briefing_material(self) -> None:
        cases = (
            ("kpop-photo", "kpop", "K-POP", "아이브, 새 앨범 콘셉트 포토 공개", "아이브가 8월 21일 새 앨범 콘셉트 포토를 공식 SNS에 공개했다."),
            ("kpop-playlist", "kpop", "K-POP", "BTS, 여름 플레이리스트 공개", "BTS 멤버가 8월 21일 직접 고른 여름 플레이리스트를 공개했다."),
            ("kpop-fansign", "kpop", "K-POP", "그룹 아이브, 팬사인회 성황", "그룹 아이브가 8월 21일 팬사인회를 진행했고 행사를 마쳤다."),
            ("ai-interview", "ai_tech", "OpenAI", "OpenAI CEO AI 인터뷰 영상 공개", "OpenAI CEO의 AI 산업 인터뷰 영상이 8월 21일 공개됐다."),
            ("kbo-schedule", "kbo_hanwha", "KBO", "KBO, 8월 21일 한화-LG 경기 일정 공개", "KBO가 8월 21일 한화와 LG의 정규시즌 경기 일정을 공개했다."),
            ("psat-study", "psat_recruitment", "PSAT", "PSAT 합격 공부법 영상 공개", "PSAT 합격 공부법을 설명하는 영상이 8월 21일 공개됐다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertFalse(assessment.qualified, title)
            self.assertIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)

    def test_material_soft_events_are_not_materiality_rejected(self) -> None:
        cases = (
            ("kpop-comeback", "kpop", "K-POP", "권은비, 9월 3일 컴백 확정", "권은비가 9월 3일 새 디지털 싱글을 발매하며 컴백한다고 발표했다."),
            ("kpop-next-month", "kpop", "K-POP", "권은비, 1년 4개월 공백 깨고 내달 컴백", "권은비가 내달 새 디지털 싱글을 발매하며 1년 4개월 만에 컴백한다."),
            ("ai-model", "ai_tech", "OpenAI", "OpenAI 새 AI 모델 공개", "OpenAI가 8월 21일 새 AI 모델을 공개하고 서비스 적용 계획을 발표했다."),
            ("ai-personnel", "ai_tech", "OpenAI", "OpenAI Replaces Chief Revenue Officer After Just 8 Months", "OpenAI replaced its chief revenue officer after eight months."),
            ("ai-selection", "ai_tech", "NVIDIA", "코팅솔루션포유, NVIDIA 협업 프로그램 선정", "코팅솔루션포유가 NVIDIA 협업 프로그램 참여사로 선정됐다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertNotIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)
            self.assertTrue(assessment.event.passed, (title, assessment.reasons))

    def test_strong_event_families_remain_eligible(self) -> None:
        cases = (
            ("economy-policy", "economy", "금융당국", "금융당국 레버리지 ETF 투자한도 100만원 규제 시행", "금융당국이 레버리지 ETF 투자한도를 100만원으로 제한하는 규제를 8월 21일부터 시행한다고 발표했다."),
            ("kbo-result", "kbo_hanwha", "한화 이글스", "한화 이글스 5-3 승리, 노시환 2홈런", "한화 이글스가 5-3으로 승리했고 노시환이 2홈런을 기록했다."),
            ("psat-competition", "psat_recruitment", "7급 공채", "지방공무원 7급 공채 경쟁률 71.5대1", "38명 선발에 1,461명이 지원해 경쟁률 71.5대1을 기록했다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertNotIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)
            self.assertTrue(assessment.qualified, (title, assessment.reasons, assessment.final_score))

    def test_low_information_primary_focus_cannot_hide_in_strong_event_family(self) -> None:
        rejected = (
            ("kpop-release-background", "kpop", "K-POP", "아이브, 신곡 발매 기념 댄스 챌린지 공개", "아이브가 신곡 발매를 기념해 댄스 챌린지 영상을 공개했다."),
            ("ai-release-background", "ai_tech", "OpenAI", "OpenAI 새 AI 모델 출시 기념 CEO 인터뷰 영상 공개", "OpenAI가 새 AI 모델 출시를 기념해 CEO 인터뷰 영상을 공개했다."),
            ("psat-study-strong", "psat_recruitment", "7급 공채", "7급 공채 PSAT 합격 공부법 영상 공개", "7급 공채 PSAT 합격 공부법을 설명하는 영상을 공개했다."),
        )
        for key, topic_id, query, title, summary in rejected:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertFalse(assessment.qualified, (title, assessment.event.event_type, assessment.reasons))
            self.assertIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)

        kept = self.assessment(
            "ai-real-release-with-interview",
            "ai_tech",
            "OpenAI",
            "OpenAI 새 AI 모델 출시, CEO 인터뷰도 공개",
            "OpenAI가 8월 21일 새 AI 모델을 출시했고 CEO 인터뷰도 공개했다.",
        )
        self.assertNotIn("LOW_BRIEFING_MATERIALITY", kept.reasons)
        self.assertTrue(kept.event.passed)

    def test_intentional_materiality_rejection_is_not_false_empty_recall_risk(self) -> None:
        story = item("low-materiality-only", "kpop", "K-POP", "아이브, 새 앨범 콘셉트 포토 공개", "아이브가 8월 21일 새 앨범 콘셉트 포토를 공식 SNS에 공개했다.")
        result = select_clusters(
            (StoryCluster("kpop", (story,)),),
            TOPICS,
            limit=10,
            now=datetime.fromisoformat("2026-08-21T14:00:00+09:00"),
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.strong_rejected_candidates, 0)
        self.assertFalse(result.filter_collapse)
        self.assertEqual(result.audit[0]["reason"], "LOW_BRIEFING_MATERIALITY")


if __name__ == "__main__":
    unittest.main()
