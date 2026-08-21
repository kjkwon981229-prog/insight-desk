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
        candidate_budget=6,
        intent_anchors=("KBO", "프로야구", "한화", "야구"),
        event_terms=("일정", "시구", "승리"),
    )


def _item(title: str, summary: str) -> NewsItem:
    return NewsItem(
        evidence_id="live-first-pitch-victory-wording",
        topic_id="kbo_hanwha",
        query="한화 야구",
        title=title,
        summary=summary,
        original_url="https://example.com/live-first-pitch-victory-wording",
        naver_url="",
        canonical_url="https://example.com/live-first-pitch-victory-wording",
        published_at="2026-08-21T13:53:00+09:00",
        source_domain="example.com",
        content_hash="live-first-pitch-victory-wording",
        score=70.0,
        metadata_title=title,
        metadata_description=summary,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=("kbo_hanwha",),
        retrieval_channels=("SIM",),
    )


class CeremonialAppearanceRegressionTests(unittest.TestCase):
    def test_victory_wish_does_not_promote_first_pitch_to_scheduled_event(self) -> None:
        item = _item(
            "프로미스나인 출신 이서연, 대전서 시구…한화 이글스 승리 기원",
            "이서연이 22일 LG-한화전에서 한화 이글스의 승리를 기원하는 시구에 나선다.",
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _topic())
        self.assertEqual(assessment.event_type, "LOW_VALUE_APPEARANCE")
        self.assertFalse(assessment.passed)


if __name__ == "__main__":
    unittest.main()
