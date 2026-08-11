from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from insight_desk.collectors.enrichment import parse_html_metadata
from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_relevance
from insight_desk.pipeline.selection import select_clusters, topic_diverse_enrichment_candidates
from insight_desk.pipeline.synthesis import synthesize_cluster
from insight_desk.pipeline.semantics import recruitment_event_type, summary_information_gain


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


    def test_incomplete_fact_bundle_is_prioritized_for_bounded_enrichment(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = replace(
            _item(
                "경기도, 지방노동감독관 7급 공채 경쟁률 11.7 대 1",
                "경기도의 첫 지방노동감독관 7급 공개경쟁 채용시험 경쟁률이 11대 1을 넘은 것으로 나타났습니다. 오늘...",
            ),
            provenance=(EvidenceType.SEARCH_SNIPPET,),
        )
        cluster = StoryCluster("psat_recruitment", (item,))
        preliminary = select_clusters((cluster,), topics, limit=10)
        # A ratio-only search result is an explicit enrichment gap, not a
        # complete strong event mysteriously lost by synthesis.
        self.assertEqual(preliminary.strong_rejected_candidates, 0)
        self.assertEqual(preliminary.enrichment_candidates, (cluster,))
        targets = topic_diverse_enrichment_candidates(
            (item,),
            topics,
            limit=5,
            priority_clusters=preliminary.enrichment_candidates,
        )
        self.assertEqual(targets, (item,))

    def test_award_subject_uses_repeated_artist_not_headline_decoration(self) -> None:
        titles = (
            "음악 보부상 스트레이 키즈, 차트 휩쓰는 중",
            "스트레이 키즈, THIS & THAT 국내외 음악 차트 1위",
            "스트레이 키즈, 컴백부터 국내외 차트 1위",
        )
        items = tuple(
            NewsItem(
                f"kpop-{index}",
                "kpop",
                "음악 차트",
                title,
                title,
                f"https://publisher-{index}.test/story",
                f"https://publisher-{index}.test/story",
                f"https://publisher-{index}.test/story",
                None,
                f"publisher-{index}.test",
                f"kpop-{index}",
                80.0,
                provenance=(EvidenceType.SEARCH_SNIPPET,),
                retrieval_channels=("SIM",),
                retrieval_queries=("음악 차트",),
            )
            for index, title in enumerate(titles, 1)
        )
        cluster = StoryCluster("kpop", items)
        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="엔터·음악·K-POP",
            trend_metrics=(),
            event_type_override="AWARD_CHART",
        )
        self.assertEqual(facts.subject, "스트레이 키즈")
        self.assertIn("스트레이 키즈", summary)
        self.assertIn("1위", summary)
        self.assertIn("컴백 후", summary)
        self.assertNotIn("컴백부터", summary)
        self.assertTrue(summary_information_gain("스트레이 키즈, THIS & THAT 국내외 음악 차트 1위", summary))

    def test_award_cluster_survives_when_result_headline_beats_supporting_headline(self) -> None:
        titles = (
            "음악 보부상 스트레이 키즈, 차트 휩쓰는 중",
            "스트레이 키즈, THIS & THAT 국내외 음악 차트 1위",
            "스트레이 키즈, 컴백부터 국내외 차트 1위",
        )
        items = tuple(
            NewsItem(
                f"kpop-score-{index}",
                "kpop",
                "음악 차트",
                title,
                title,
                f"https://score-publisher-{index}.test/story",
                f"https://score-publisher-{index}.test/story",
                f"https://score-publisher-{index}.test/story",
                None,
                f"score-publisher-{index}.test",
                f"kpop-score-{index}",
                float(60 + index * 10),
                provenance=(EvidenceType.SEARCH_SNIPPET,),
                retrieval_channels=("SIM",),
                retrieval_queries=("음악 차트",),
            )
            for index, title in enumerate(titles)
        )
        topics, _ = load_topics(Path("config/topics.json"))
        result = select_clusters((StoryCluster("kpop", items),), topics, limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertFalse(result.filter_collapse)
        self.assertNotIn("SYNTHESIS_FACT_LOSS", result.audit[0]["selection_reasons"])


    def test_live_like_award_decoration_does_not_become_artist_subject(self) -> None:
        titles = (
            "8월도 No.1 임영웅, 아이돌 차트 평점랭킹 280주 연속 1위",
            "임영웅, 아이돌 차트 평점랭킹 280주 연속 1위",
            "임영웅 280주 연속 아이돌 차트 1위",
        )
        items = tuple(
            replace(
                _item(title, title),
                source_domain=f"publisher-{index}.test",
                original_url=f"https://publisher-{index}.test/story",
                canonical_url=f"https://publisher-{index}.test/story",
            )
            for index, title in enumerate(titles, 1)
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kpop", items),
            topic_name="엔터·음악·K-POP",
            trend_metrics=(),
            event_type_override="AWARD_CHART",
        )
        self.assertEqual(facts.subject, "임영웅")
        self.assertIn("임영웅이", summary)
        self.assertNotIn("아이돌가", summary)

    def test_directional_earnings_percent_strips_decoration_and_keeps_binding(self) -> None:
        cases = (
            ("'어화둥둥 우리 GPU' NHN 영업이익 164% 증가", "NHN"),
            ("NHN클라우드, AI GPU 성과로 매출 85% 증가", "NHN클라우드"),
        )
        for index, (title, subject) in enumerate(cases, 1):
            _, summary, _, _, facts, _ = synthesize_cluster(
                StoryCluster(
                    "economy",
                    (_item(title, title),),
                ),
                topic_name="경제·투자",
                trend_metrics=(),
                event_type_override="EARNINGS",
            )
            self.assertEqual(facts.subject, subject)
            self.assertIn(subject, summary)
            self.assertIn("% 증가", summary)
            self.assertNotIn("%를 기록", summary)

    def test_numeric_recruitment_ratio_is_competition_not_generic_application(self) -> None:
        self.assertEqual(
            recruitment_event_type("부산시, 올 지방공무원 7급 공채 71.5대 1"),
            "RECRUITMENT_COMPETITION",
        )

if __name__ == "__main__":
    unittest.main()
