from __future__ import annotations

import unittest
from datetime import datetime

from insight_desk.domain.models import KeywordGroup, NewsItem, TrendPoint
from insight_desk.domain.models import Topic
from insight_desk.pipeline.clustering import cluster_news
from insight_desk.pipeline.deduplication import deduplicate_news
from insight_desk.pipeline.normalization import normalize_news_item, normalize_url
from insight_desk.pipeline.scoring import score_news
from insight_desk.pipeline.semantics import metric_observations
from insight_desk.pipeline.trend_metrics import compute_trend_metrics


class PipelineTests(unittest.TestCase):
    def test_html_and_url_normalization(self) -> None:
        item = normalize_news_item(
            {
                "title": "<b>제목</b> &amp; 추가",
                "description": "요약  여러   칸",
                "originallink": "HTTPS://Example.COM/path?utm_source=x&keep=1#frag",
                "link": "https://n.news.naver.com/x",
                "pubDate": "Sun, 09 Aug 2026 08:00:00 +0900",
            },
            topic_id="t",
            query="제목",
            evidence_id="N001",
        )
        self.assertEqual(item.title, "제목 & 추가")
        self.assertEqual(item.canonical_url, "https://example.com/path?keep=1")
        self.assertIn("+09:00", item.published_at or "")

    def test_duplicate_url_and_title_are_collapsed(self) -> None:
        first = NewsItem("N001", "t", "q", "같은 제목", "짧은", "https://a.test", "", "https://a.test", None, "a.test", "a")
        second = NewsItem("N002", "t", "q", "같은 제목", "더 긴 요약", "https://a.test", "", "https://a.test", None, "a.test", "b")
        result = deduplicate_news((first, second))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].summary, "더 긴 요약")

    def test_trend_metrics_do_not_compare_batches(self) -> None:
        points = (
            TrendPoint("a", "A", "t", "2026-08-08", 10, "batch-a"),
            TrendPoint("a", "A", "t", "2026-08-09", 20, "batch-a"),
            TrendPoint("b", "B", "t", "2026-08-08", 90, "batch-b"),
            TrendPoint("b", "B", "t", "2026-08-09", 80, "batch-b"),
        )
        metrics = compute_trend_metrics(points)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0].delta, 10)
        self.assertEqual(metrics[1].delta, -10)
        self.assertIsNone(getattr(metrics[0], "cross_batch_ratio", None))

    def test_trend_materiality_distinguishes_tiny_delta_from_rise(self) -> None:
        points = (
            TrendPoint("flat", "Flat", "t", "2026-08-08", 50.0, "batch-flat"),
            TrendPoint("flat", "Flat", "t", "2026-08-09", 50.2, "batch-flat"),
            TrendPoint("rise", "Rise", "t", "2026-08-08", 20.0, "batch-rise"),
            TrendPoint("rise", "Rise", "t", "2026-08-09", 22.0, "batch-rise"),
        )
        metrics = {metric.group_id: metric for metric in compute_trend_metrics(points)}
        self.assertEqual(metrics["flat"].state, "NO_MEANINGFUL_CHANGE")
        self.assertEqual(metrics["rise"].state, "RISE")

    def test_metric_observation_binds_period_to_each_instrument(self) -> None:
        observations = metric_observations("2026년 6월 코스닥 +6.97% 급등, 코스피 +0.65% 상승")
        self.assertEqual(
            [(value.instrument, value.value, value.direction, value.period) for value in observations],
            [("코스닥", "+6.97%", "급등", "2026년6월"), ("코스피", "+0.65%", "상승", "2026년6월")],
        )

    def test_clustering_and_scoring_are_deterministic(self) -> None:
        first = NewsItem("N001", "t", "AI", "AI 에이전트 기업 발표", "업무 활용", "https://a.test", "", "https://a.test", "2026-08-09T08:00:00+09:00", "a.test", "a")
        second = NewsItem("N002", "t", "AI", "AI 에이전트 기업 발표 후속", "추가 내용", "https://b.test", "", "https://b.test", "2026-08-09T07:00:00+09:00", "b.test", "b")
        scored = score_news(
            (first, second),
            (Topic("t", "테스트", True, False, 50, ("AI",)),),
            now=datetime.fromisoformat("2026-08-09T09:00:00+09:00"),
        )
        clusters = cluster_news(scored)
        self.assertEqual(len(clusters), 1)
        self.assertGreaterEqual(clusters[0].representative.score, 0)
