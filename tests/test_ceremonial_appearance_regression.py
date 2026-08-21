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
        event_terms=("일정", "시구", "승리", "연승"),
    )


def _item(key: str, title: str, summary: str) -> NewsItem:
    return NewsItem(
        evidence_id=key,
        topic_id="kbo_hanwha",
        query="한화 야구",
        title=title,
        summary=summary,
        original_url=f"https://example.com/{key}",
        naver_url="",
        canonical_url=f"https://example.com/{key}",
        published_at="2026-08-21T13:53:00+09:00",
        source_domain="example.com",
        content_hash=key,
        score=70.0,
        metadata_title=title,
        metadata_description=summary,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=("kbo_hanwha",),
        retrieval_channels=("SIM",),
    )


class CeremonialAppearanceRegressionTests(unittest.TestCase):
    def test_victory_wording_does_not_promote_first_pitch_to_scheduled_event(self) -> None:
        item = _item(
            "victory-fairy-first-pitch",
            "프로미스나인 출신 이서연, 대전서 시구…한화 이글스 승리 요정 도전",
            "이서연이 22일 LG-한화전에서 한화 이글스의 승리를 기원하는 시구에 나선다.",
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _topic())
        self.assertEqual(assessment.event_type, "LOW_VALUE_APPEARANCE")
        self.assertFalse(assessment.passed)

    def test_real_sports_result_keeps_precedence_over_ceremonial_tail(self) -> None:
        item = _item(
            "real-result-with-first-pitch-tail",
            "한화 5연승, 이서연 시구 뒤 LG전 승리",
            "한화가 LG전에서 승리해 5연승을 기록했고 경기 전 이서연이 시구했다.",
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _topic())
        self.assertEqual(assessment.event_type, "SPORTS_RESULT")
        self.assertTrue(assessment.passed)


if __name__ == "__main__":
    unittest.main()
