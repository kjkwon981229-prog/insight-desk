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
from insight_desk.pipeline.analysis import _story_trend_matches
from insight_desk.pipeline.clustering import StoryCluster, cluster_news
from insight_desk.pipeline.deduplication import deduplicate_news
from insight_desk.pipeline.normalization import normalize_news_payloads
from insight_desk.pipeline.selection import (
    cap_topic_candidates,
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
    summary: str = "해당 변화가 8월 10일 공식 발표됐고 적용 일정이 공개됐다.",
) -> NewsItem:
    provenance = (EvidenceType.SEARCH_SNIPPET, EvidenceType.OFFICIAL_SOURCE) if official else (EvidenceType.SEARCH_SNIPPET,)
    return NewsItem(
        f"N-{key}", topic_id, topic_id, f"{topic_id} 모델 출시 발표 {key}", summary,
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

    def test_zero_story_result_is_explicitly_valid_empty_day(self) -> None:
        status = CollectorStatus(1, 1, 0, False, 1)
        state = RunState(
            RunStatus.COMPLETE,
            True,
            "2026-08-10T07:00:00+09:00",
            "2026-08-10",
            "fixture",
            status,
            status,
        )
        weak = replace(
            _item("empty", "ai", score=10.0),
            title="일반 소식",
            summary="추가 사실이 없는 짧은 안내다.",
        )
        briefing = build_briefing(
            state=state,
            topics=_topics(),
            news=(weak,),
            clusters=(StoryCluster("ai", (weak,)),),
            trend_metrics=(),
            generated_at=datetime.fromisoformat("2026-08-10T07:00:00+09:00"),
        )
        self.assertEqual(briefing.stories, ())
        self.assertEqual(briefing.editorial_health, "VALID_EMPTY_DAY")
        self.assertEqual(briefing.state.status, RunStatus.VALID_EMPTY_DAY)
        self.assertTrue(briefing.state.publish)

    def test_story_trend_requires_configured_alias_not_group_label(self) -> None:
        from insight_desk.domain.models import TrendMetric

        metric = TrendMetric(
            "internal-id", "Internal group label", "ai", "batch", 20.0, 10.0,
            None, 10.0, 100.0, None, "직전 구간보다 상승", aliases=("actual term",),
        )
        matching = replace(
            _item("trend-match", "ai"),
            title="Actual term 모델 발표",
            summary="Actual term 모델의 발표 내용이 공개됐다.",
        )
        label_only = replace(
            _item("trend-label-only", "ai"),
            title="Internal group label 모델 발표",
            summary="내부 그룹 이름만 언급된 발표다.",
        )
        self.assertEqual(_story_trend_matches(StoryCluster("ai", (matching,)), (metric,)), (metric,))
        self.assertEqual(_story_trend_matches(StoryCluster("ai", (label_only,)), (metric,)), ())

    def test_irrelevant_low_signal_candidate_is_not_used_as_filler(self) -> None:
        candidate = replace(
            _item("noise", "psat", score=90.0),
            query="PSAT",
            title="지역 행사 소식",
            summary="현장 소식만 전해졌다.",
        )
        result = select_clusters((StoryCluster("psat", (candidate,)),), _topics(), limit=10)
        self.assertEqual(result.selected, ())

    def test_generic_synthesis_output_is_not_selected(self) -> None:
        candidate = replace(
            _item(
                "generic-market",
                "economy",
                score=100.0,
                summary="코스피 상승 모멘텀을 찾지 못했다. 1일 기준 흐름이다.",
            ),
            query="코스피",
            title="반도체 폭락장 속 코스피 역행",
        )
        result = select_clusters((StoryCluster("economy", (candidate,)),), _topics(), limit=10)
        self.assertEqual(result.selected, ())
        self.assertIn(
            "SYNTHESIS_NOT_EDITORIAL_READY",
            result.audit[0]["selection_reasons"],
        )

    def test_duplicate_rendered_headline_is_not_selected_twice(self) -> None:
        first = replace(
            _item("headline-a", "ai", score=90.0, domain="first.example"),
            title="AI 모델 출시 발표",
            summary="AI 모델이 8월 10일 출시됐다는 구체적인 발표가 확인됐다.",
        )
        second = replace(
            _item("headline-b", "ai", score=60.0, domain="second.example"),
            title="AI 모델 출시 발표",
            summary="AI 모델이 8월 10일 출시됐다는 구체적인 발표가 확인됐다.",
        )
        result = select_clusters(
            (StoryCluster("ai", (first,)), StoryCluster("ai", (second,))),
            _topics(),
            limit=10,
        )
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.selected[0].representative.title, "AI 모델 출시 발표")
        rejected = [entry for entry in result.audit if entry.get("selected") is False]
        self.assertTrue(any(entry.get("reason") == "duplicate rendered headline" for entry in rejected))

    def test_metadata_policy_tail_does_not_promote_analyst_commentary(self) -> None:
        candidate = replace(
            _item(
                "analyst-commentary",
                "ai",
                score=100.0,
                summary="메모리 반도체주의 조정이 마무리 단계이며 투자 재진입 기회라고 분석했다.",
            ),
            query="반도체",
            title="모건스탠리 \"메모리 반도체주 조정 끝...지금이 재진입 기회\"",
            metadata_title="모건스탠리 \"메모리 반도체주 조정 끝...지금이 재진입 기회\"",
            metadata_description="최근 주가 급락을 분석하며 주주환원 정책을 반등의 핵심으로 꼽고 투자 매력을 강조했다.",
        )
        result = select_clusters((StoryCluster("ai", (candidate,)),), _topics(), limit=10)
        self.assertEqual(result.selected, ())

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

    def test_cross_query_dedupe_preserves_retrieval_provenance(self) -> None:
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
        normalized = normalize_news_payloads(
            (("ai", "AI", "SIM", payload), ("ai", "생성형 AI", "DATE", payload))
        )
        merged = deduplicate_news(normalized)
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0].retrieval_queries), {"AI", "생성형 AI"})

    def test_candidate_budget_uses_semantic_topic_match_not_incidental_attribution(self) -> None:
        topic_a = Topic(
            "alpha", "Alpha", True, False, 60, ("Alpha",), candidate_budget=1,
            intent_anchors=("Alpha",), event_terms=("발표",),
        )
        topic_b = Topic(
            "beta", "Beta", True, False, 60, ("Beta",), candidate_budget=1,
            intent_anchors=("Beta",), event_terms=("발표",),
        )
        candidate = replace(
            _item("budget", "alpha", matched=("alpha", "beta")),
            query="Alpha",
            title="Alpha 모델 출시 발표",
            summary="Alpha 모델 출시 일정과 적용 범위가 발표됐다.",
        )
        bounded = cap_topic_candidates((candidate,), (topic_a, topic_b))
        self.assertEqual(len(bounded), 1)
        self.assertEqual(bounded[0].matched_topic_ids, ("alpha",))

    def test_semantic_attribution_does_not_use_another_topic_query_as_evidence(self) -> None:
        topic_a = Topic(
            "alpha", "Alpha", True, False, 60, ("Alpha",), candidate_budget=1,
            intent_anchors=("Alpha",), event_terms=("발표",),
        )
        # The two topics deliberately share the retrieval query.  Beta must
        # not inherit an Alpha story merely because that query was used for
        # discovery.
        topic_b = Topic(
            "beta", "Beta", True, False, 60, ("Alpha",), candidate_budget=1,
            intent_anchors=("Beta",), event_terms=("발표",),
        )
        candidate = replace(
            _item("shared-query", "alpha", matched=("alpha", "beta")),
            query="Alpha",
            title="Alpha 모델 출시 발표",
            summary="Alpha 모델 출시 일정과 적용 범위가 발표됐다.",
        )
        bounded = cap_topic_candidates((candidate,), (topic_a, topic_b))
        self.assertEqual(bounded[0].matched_topic_ids, ("alpha",))

    def test_story_attribution_rechecks_cross_topic_intent(self) -> None:
        economy = Topic(
            "economy",
            "경제·투자",
            True,
            False,
            75,
            ("코스피",),
            intent_anchors=("코스피",),
            event_terms=("상승",),
        )
        kbo = Topic(
            "kbo",
            "KBO·한화 이글스",
            True,
            True,
            65,
            ("한화 경기",),
            intent_anchors=("한화 이글스", "한화 경기", "한화 야구", "KBO", "프로야구", "야구"),
            event_terms=("경기", "승리", "부상"),
            required_intent_terms=("한화", "한화 이글스", "한화 경기", "KBO", "프로야구"),
        )
        item = replace(
            _item(
                "cross-topic-company",
                "economy",
                score=90.0,
                summary="코스피가 0.76% 상승했고 한화에어로스페이스가 관련 종목으로 언급됐다.",
            ),
            query="코스피",
            title="코스피 0.76% 상승",
            metadata_title="코스피 0.76% 상승",
            metadata_description="코스피가 0.76% 상승했고 한화에어로스페이스가 관련 종목으로 언급됐다.",
            matched_topic_ids=("economy", "kbo"),
        )
        status = CollectorStatus(1, 1, 0, False, 1)
        state = RunState(
            RunStatus.COMPLETE,
            True,
            "2026-08-10T07:00:00+09:00",
            "2026-08-10",
            "fixture",
            status,
            status,
        )
        briefing = build_briefing(
            state=state,
            topics=(economy, kbo),
            news=(item,),
            clusters=(StoryCluster("economy", (item,)),),
            trend_metrics=(),
            generated_at=datetime.fromisoformat("2026-08-10T07:00:00+09:00"),
        )
        self.assertEqual(len(briefing.stories), 1)
        self.assertEqual(briefing.stories[0].matched_topic_ids, ("economy",))

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

    def test_psat_scope_is_explicit_and_includes_local_seventh_grade_events(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        psat = next(topic for topic in topics if topic.id == "psat_recruitment")
        self.assertEqual(psat.scope, "national_and_local_civil_service")

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
