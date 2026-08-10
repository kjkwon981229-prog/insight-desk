from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from insight_desk.collectors.enrichment import parse_html_metadata
from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_relevance
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.synthesis import synthesize_cluster


def _item(title: str, summary: str, *, metadata_title: str = "", metadata_description: str = "") -> NewsItem:
    return NewsItem(
        "run83",
        "psat_recruitment",
        "7급 공채",
        title,
        summary,
        "https://publisher.test/story",
        "https://news.naver.com/story",
        "https://publisher.test/story",
        None,
        "publisher.test",
        "run83",
        80.0,
        metadata_title=metadata_title,
        metadata_description=metadata_description,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        retrieval_channels=("SIM",),
        retrieval_queries=("7급 공채",),
    )


class Run83RegressionTests(unittest.TestCase):
    def test_structured_article_facts_survive_selection_and_synthesis(self) -> None:
        body = """
        <meta property="og:title" content="경기도, 지방노동감독관 7급 공채 경쟁률 11.7 대 1">
        <meta property="og:description" content="경기도의 첫 지방노동감독관 7급 공채 경쟁률이 11대 1을 넘었습니다. 오늘...">
        <script type="application/ld+json">
        {"@type":"NewsArticle", "headline":"경기도, 지방노동감독관 7급 공채 경쟁률 11.7 대 1", "description":"경기도의 첫 지방노동감독관 7급 공개경쟁 채용시험 경쟁률이 11대 1을 넘었습니다. 25명을 선발하는 노동 직류에 292명이 지원했습니다."}
        </script>
        """.encode("utf-8")
        metadata = parse_html_metadata(body, url="https://publisher.test/story")
        item = _item(
            "경기도 첫 지방노동감독관 7급 공채 경쟁률 11.7대 1",
            "경기도 첫 지방노동감독관 7급 공채 경쟁률 11.7대 1",
            metadata_title=metadata.title,
            metadata_description=metadata.description,
        )
        topics, _ = load_topics(Path("config/topics.json"))
        cluster = StoryCluster("psat_recruitment", (item,))
        result = select_clusters((cluster,), topics, limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertFalse(result.filter_collapse)
        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="PSAT·공채 일정",
            trend_metrics=(),
            event_type_override="RECRUITMENT_COMPETITION",
        )
        self.assertIn("25명", summary)
        self.assertIn("292명", summary)
        self.assertIn("경기도", facts.subject)
        self.assertNotEqual(facts.subject, "경기")

    def test_procedural_거쳐_survives_but_biographical_phrase_is_rejected(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        topic = next(topic for topic in topics if topic.id == "psat_recruitment")
        positive = _item(
            "경기도 지방노동감독관 7급 공채 경쟁률 11.7대 1",
            "필기·면접 시험을 거쳐 최종합격자는 12월 21일 발표한다. 25명을 선발했고 292명이 지원했다.",
            metadata_title="경기도 지방노동감독관 7급 공채 경쟁률 11.7대 1",
            metadata_description="필기·면접 시험을 거쳐 최종합격자는 12월 21일 발표한다. 25명을 선발했고 292명이 지원했다.",
        )
        negative = replace(
            positive,
            title="보건진료소장 경력 소개",
            summary="2014년 공무원 시험을 거쳐 보건진료소장이 됐다.",
            metadata_title="보건진료소장 경력 소개",
            metadata_description="2014년 공무원 시험을 거쳐 보건진료소장이 됐다.",
        )
        self.assertTrue(assess_relevance(StoryCluster("psat_recruitment", (positive,)), topic).passed)
        self.assertFalse(assess_relevance(StoryCluster("psat_recruitment", (negative,)), topic).passed)


if __name__ == "__main__":
    unittest.main()
