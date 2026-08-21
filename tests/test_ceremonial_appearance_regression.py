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
        original_url="https://www.starnewskorea.com/music/2026/08/21/2026082113530654094",
        naver_url="https://m.entertain.naver.com/article/108/0003464048",
        canonical_url="https://www.starnewskorea.com/music/2026/08/21/2026082113530654094",
        published_at="2026-08-21T13:55:00+09:00",
        source_domain="starnewskorea.com",
        content_hash="live-first-pitch-victory-wording",
        score=70.0,
        metadata_title=title,
        metadata_description=summary,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=("kbo_hanwha",),
        retrieval_channels=("SIM",),
    )


class CeremonialAppearanceRegressionTests(unittest.TestCase):
    def test_live_victory_for_wording_is_low_value_appearance(self) -> None:
        item = _item(
            '프로미스나인 출신 이서연, 대전서 시구 "한화 이글스 승리 위해"',
            "이서연은 오는 22일 대전 한화생명볼파크에서 열리는 2026 KBO 리그 한화 이글스와 LG 트윈스의 경기에 시구자로 참석한다. 이날 이서연은 한화 이글스의 승리를 기원하는 시구를 펼친다.",
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _topic())
        self.assertEqual(assessment.event_type, "LOW_VALUE_APPEARANCE")
        self.assertFalse(assessment.passed)


if __name__ == "__main__":
    unittest.main()
