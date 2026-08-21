from __future__ import annotations

import unittest

from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster


def _topic(topic_id: str = "kpop", name: str = "엔터·음악·K-POP") -> Topic:
    return Topic(
        topic_id,
        name,
        True,
        False,
        70,
        ("K-POP",),
        candidate_budget=12,
        intent_anchors=("K-POP", "가수", "그룹", "컴백", "앨범", "음원", "콘서트"),
        negative_context=("광고", "협찬", "굿즈"),
        event_terms=("발표", "공개", "앨범", "음원", "컴백", "공연", "콘서트", "수상", "계약"),
    )


def _item(key: str, title: str, *, topic_id: str = "kpop", query: str = "K-POP") -> NewsItem:
    return NewsItem(
        evidence_id=key,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=title,
        original_url=f"https://fixture.test/{key}",
        naver_url="",
        canonical_url=f"https://fixture.test/{key}",
        published_at="2026-08-21T06:30:00+09:00",
        source_domain="fixture.test",
        content_hash=key,
        score=90.0,
        metadata_title=title,
        metadata_description=title,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class KpopPromoMaterialityTests(unittest.TestCase):
    def test_promotional_performance_content_is_low_value(self) -> None:
        topic = _topic()
        titles = (
            "권은비, 아이돌 신곡 댄스 커버 공개",
            "아이브, 신예 그룹 댄스 챌린지 영상 공개",
            "가수 A, 화제곡 커버 무대 선보여",
            "그룹 B, 퍼포먼스 영상 공개",
            "그룹 C, 신곡 안무 영상 공개",
        )
        for index, title in enumerate(titles):
            assessment = assess_cluster(
                StoryCluster("kpop", (_item(f"promo-{index}", title),)),
                topic,
                novelty="NEW",
            )
            self.assertEqual(assessment.event.event_type, "LOW_VALUE_PROMO_CONTENT", title)
            self.assertFalse(assessment.event.passed, title)
            self.assertFalse(assessment.qualified, title)
            self.assertIn("LOW_VALUE_EVENT", assessment.event.reasons, title)

    def test_comeback_background_does_not_rescue_a_cover_story(self) -> None:
        topic = _topic()
        title = "컴백 앞둔 권은비, 아이돌 신곡 댄스 커버 공개"
        assessment = assess_cluster(
            StoryCluster("kpop", (_item("comeback-background", title),)),
            topic,
            novelty="NEW",
        )
        self.assertEqual(assessment.event.event_type, "LOW_VALUE_PROMO_CONTENT")
        self.assertFalse(assessment.qualified)

    def test_material_release_with_secondary_performance_video_survives(self) -> None:
        topic = _topic()
        title = "권은비, 신곡 'Hello' 발매하며 컴백·퍼포먼스 영상 공개"
        assessment = assess_cluster(
            StoryCluster("kpop", (_item("material-release", title),)),
            topic,
            novelty="NEW",
        )
        self.assertNotEqual(assessment.event.event_type, "LOW_VALUE_PROMO_CONTENT")
        self.assertTrue(assessment.event.passed)

    def test_material_tour_announcement_with_secondary_challenge_survives(self) -> None:
        topic = _topic()
        title = "BTS, 월드투어 개최 발표·댄스 챌린지 영상 공개"
        assessment = assess_cluster(
            StoryCluster("kpop", (_item("material-tour", title),)),
            topic,
            novelty="NEW",
        )
        self.assertNotEqual(assessment.event.event_type, "LOW_VALUE_PROMO_CONTENT")
        self.assertTrue(assessment.event.passed)

    def test_non_kpop_video_publication_is_not_globally_blocked(self) -> None:
        topic = Topic(
            "ai_tech",
            "AI·테크",
            True,
            False,
            90,
            ("OpenAI",),
            candidate_budget=12,
            intent_anchors=("OpenAI", "AI", "모델"),
            negative_context=("광고",),
            event_terms=("공개", "출시", "발표"),
        )
        title = "OpenAI, GPT-6 데모 영상 공개"
        assessment = assess_cluster(
            StoryCluster("ai_tech", (_item("ai-demo", title, topic_id="ai_tech", query="OpenAI"),)),
            topic,
            novelty="NEW",
        )
        self.assertNotEqual(assessment.event.event_type, "LOW_VALUE_PROMO_CONTENT")


if __name__ == "__main__":
    unittest.main()
