from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from insight_desk.collectors.collect import collect_news
from insight_desk.config import load_topics
from insight_desk.domain.models import (
    CollectorStatus,
    EvidenceType,
    NewsItem,
    RunState,
    RunStatus,
    Topic,
)
from insight_desk.pipeline.analysis import build_briefing
from insight_desk.pipeline.clustering import StoryCluster, cluster_news
from insight_desk.pipeline.deduplication import deduplicate_news
from insight_desk.pipeline.selection import (
    candidate_quality,
    select_clusters,
    topic_diverse_enrichment_candidates,
)


def _topics() -> tuple[Topic, ...]:
    return (
        Topic("ai", "AI·테크", True, False, 90, ("AI",), candidate_budget=40),
        Topic("kpop", "엔터·음악·K-POP", True, False, 70, ("K-POP",), candidate_budget=40),
        Topic("economy", "경제·투자", True, False, 75, ("환율",), candidate_budget=40),
        Topic("kbo", "KBO·한화 이글스", True, True, 65, ("한화",), candidate_budget=36),
        Topic("psat", "PSAT·공채 일정", True, True, 55, ("PSAT",), candidate_budget=36),
    )


def _item(
    key: str,
    topic_id: str,
    *,
    score: float = 50.0,
    domain: str | None = None,
    matched: tuple[str, ...] = (),
    official: bool = False,
    summary: str = "공식 발표와 여러 보도에서 핵심 일정과 변화가 확인됐다.",
) -> NewsItem:
    provenance = (EvidenceType.SEARCH_SNIPPET, EvidenceType.OFFICIAL_SOURCE) if official else (EvidenceType.SEARCH_SNIPPET,)
    return NewsItem(
        f"N-{key}", topic_id, topic_id, f"{topic_id} 주요 변화 {key}", summary,
        f"https://{domain or topic_id + '.example'}/story/{key}", "", f"https://{domain or topic_id + '.example'}/story/{key}",
        "2026-08-09T08:00:00+09:00", domain or topic_id + ".example", key, score,
        provenance=provenance, matched_topic_ids=matched or (topic_id,),
    )


def _cluster(key: str, topic_id: str, **kwargs: object) -> StoryCluster:
    return StoryCluster(topic_id, (_item(key, topic_id, **kwargs),))


class SelectionTests(unittest.TestCase):
    def test_topic_candidate_budget_is_fair_and_shared_queries_are_not_refetched(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.calls: list[tuple[str, int]] = []

            def search_news(self, query: str, *, display: int = 100, start: int = 1):
                self.calls.append((query, display))
                return {"items": [{"title": query, "description": "충분한 설명이 있는 테스트 결과입니다.", "originallink": "https://example.com/story", "link": "", "pubDate": "Sun, 09 Aug 2026 08:00:00 +0900"}]}

        client = Client()
        topics = (
            Topic("a", "A", True, False, 50, ("공통", "a"), candidate_budget=10),
            Topic("b", "B", True, False, 50, ("공통", "b"), candidate_budget=10),
        )
        collection = collect_news(client, topics)
        self.assertEqual([query for query, _ in client.calls], ["공통", "a", "b"])
        self.assertTrue(all(display <= 5 for _, display in client.calls))
        self.assertEqual(collection.status.succeeded, 3)

    def test_interest_profile_is_ssot_and_has_query_family_coverage(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        self.assertEqual([topic.id for topic in topics], ["ai_tech", "kpop", "economy", "kbo_hanwha", "psat_recruitment"])
        all_queries = {query for topic in topics for query in topic.all_news_queries}
        for expected in ("ChatGPT", "OpenAI", "생성형 AI", "SM", "JYP", "한국은행", "미국 연준", "한화 경기", "7급 공채"):
            self.assertIn(expected, all_queries)

    def test_ai_volume_does_not_monopolize_and_core_topics_survive(self) -> None:
        clusters = tuple(_cluster(f"ai-{i}", "ai") for i in range(8)) + tuple(
            _cluster(topic_id, topic_id) for topic_id in ("kpop", "economy", "kbo", "psat")
        )
        result = select_clusters(clusters, _topics(), limit=10)
        selected_topics = {cluster.topic_id for cluster in result.selected}
        self.assertTrue({"ai", "kpop", "economy", "kbo", "psat"}.issubset(selected_topics))
        self.assertLessEqual(sum(cluster.topic_id == "ai" for cluster in result.selected), 3)

    def test_conditional_topics_omit_without_meaningful_candidates(self) -> None:
        result = select_clusters(tuple(_cluster(f"ai-{i}", "ai") for i in range(4)), _topics(), limit=10)
        self.assertNotIn("kbo", {cluster.topic_id for cluster in result.selected})
        self.assertNotIn("psat", {cluster.topic_id for cluster in result.selected})
        self.assertEqual(len(result.selected), 4)

    def test_cap_relaxes_when_only_one_topic_qualifies(self) -> None:
        result = select_clusters(tuple(_cluster(f"ai-{i}", "ai") for i in range(7)), _topics(), limit=10)
        self.assertEqual(len(result.selected), 7)

    def test_cross_topic_duplicate_preserves_both_attributions(self) -> None:
        first = _item("same", "ai", matched=("ai", "economy"), domain="shared.example")
        second = replace(
            _item("same-copy", "economy", matched=("economy",), domain="shared.example"),
            original_url=first.original_url,
            canonical_url=first.canonical_url,
            content_hash=first.content_hash,
        )
        merged = deduplicate_news((first, second))
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0].matched_topic_ids), {"ai", "economy"})
        clusters = cluster_news(merged)
        result = select_clusters(clusters, _topics(), limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(set(result.selected[0].items[0].matched_topic_ids), {"ai", "economy"})

    def test_source_diversity_beats_raw_source_volume(self) -> None:
        syndicated = StoryCluster(
            "ai",
            tuple(_item(f"copy-{i}", "ai", domain="one.example") for i in range(6)),
        )
        diverse = StoryCluster(
            "kpop",
            tuple(_item(f"diverse-{i}", "kpop", domain=f"pub-{i}.example") for i in range(2)),
        )
        self.assertGreater(candidate_quality(diverse, _topics()[1]), candidate_quality(syndicated, _topics()[0]))

    def test_enrichment_targets_are_topic_diverse(self) -> None:
        items = tuple(_item(f"ai-{i}", "ai") for i in range(5)) + tuple(
            _item(topic_id, topic_id) for topic_id in ("kpop", "economy", "kbo", "psat")
        )
        selected = topic_diverse_enrichment_candidates(items, _topics(), limit=5)
        self.assertEqual({selected_item.topic_id for selected_item in selected}, {"ai", "kpop", "economy", "kbo", "psat"})

    def test_selection_audit_explains_rejection_and_selection(self) -> None:
        result = select_clusters(tuple(_cluster(f"ai-{i}", "ai") for i in range(5)), _topics(), limit=3)
        self.assertTrue(result.audit)
        self.assertTrue(any(entry["selected"] is True for entry in result.audit))
        self.assertTrue(any(entry["selected"] is False for entry in result.audit))
        self.assertTrue(all("reason" in entry and "source_diversity" in entry for entry in result.audit))

    def test_overview_is_lineup_level_not_first_story_summary(self) -> None:
        status = CollectorStatus(1, 1, 0, False, 2)
        state = RunState(RunStatus.COMPLETE, True, "2026-08-09T08:00:00+09:00", "2026-07-10", "fixture", status, status)
        briefing = build_briefing(
            state=state,
            topics=_topics(),
            news=tuple(_item(f"{topic}-1", topic) for topic in ("ai", "economy")),
            clusters=(_cluster("ai-1", "ai"), _cluster("economy-1", "economy")),
            trend_metrics=(),
            generated_at=datetime.fromisoformat("2026-08-09T08:00:00+09:00"),
        )
        self.assertTrue(briefing.three_line_summary[0].startswith("오늘 확인할 가치가 있는"))
        self.assertNotEqual(briefing.three_line_summary[0], briefing.stories[0].summary)

    def test_ten_day_matrix_has_no_forced_filler(self) -> None:
        days = (
            ("ai", 8), ("economy", 8), ("kpop", 4), ("kbo", 3), ("psat", 3),
            ("none", 0), ("ai", 1), ("economy", 1), ("kpop", 2), ("psat", 1),
        )
        for topic_id, count in days:
            clusters = tuple(_cluster(f"{topic_id}-{index}", topic_id) for index in range(count)) if topic_id != "none" else ()
            result = select_clusters(clusters, _topics(), limit=10)
            self.assertLessEqual(len(result.selected), count, topic_id)
            if topic_id == "none":
                self.assertEqual(result.selected, ())


if __name__ == "__main__":
    unittest.main()
