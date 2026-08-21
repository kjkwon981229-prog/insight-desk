from __future__ import annotations

import unittest

from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_event


def _topic() -> Topic:
    return Topic(
        "kbo_hanwha",
        "KBO·한화 이글스",
        True,
        True,
        50,
        ("한화 야구", "한화 이글스"),
        candidate_budget=12,
        intent_anchors=("KBO", "프로야구", "한화", "야구"),
        event_terms=("출범", "발표", "위원회"),
    )


def _item() -> NewsItem:
    title = "KBO, 한국야구 명예의 전당 선정위원회 출범"
    truncated_live_lead = (
        "KBO는 21일 한국야구 명예의 전당 선정위원회를 공식 출범했다고 밝혔다. "
        "선정위원장으로는 홍윤표 OSEN 선임기자, 선정위원으로는 민경삼 프로야구 SSG 랜더스 고문과 "
        "이태일 프레인스포츠 부사장, 윤병웅 KBO 비디오..."
    )
    return NewsItem(
        evidence_id="kbo-hall-of-fame-committee-launch",
        topic_id="kbo_hanwha",
        query="한화 야구",
        title=title,
        summary=truncated_live_lead,
        original_url="https://example.com/kbo-hall-of-fame-committee-launch",
        naver_url="",
        canonical_url="https://example.com/kbo-hall-of-fame-committee-launch",
        published_at="2026-08-21T18:00:00+09:00",
        source_domain="example.com",
        content_hash="kbo-hall-of-fame-committee-launch",
        score=70.0,
        metadata_title=title,
        metadata_description=truncated_live_lead,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=("kbo_hanwha",),
        retrieval_channels=("SIM",),
    )


class OrganizationLaunchRegressionTests(unittest.TestCase):
    def test_kbo_committee_launch_is_a_typed_material_event_even_with_truncated_lead(self) -> None:
        assessment = assess_event(StoryCluster("kbo_hanwha", (_item(),)), _topic())
        self.assertNotEqual(assessment.event_type, "OTHER")
        self.assertTrue(assessment.passed)
        self.assertTrue(assessment.action)


if __name__ == "__main__":
    unittest.main()
