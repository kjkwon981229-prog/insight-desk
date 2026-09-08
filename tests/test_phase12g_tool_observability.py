from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.acquisition.discovery import DiscoveryError, SequentialNewsDiscovery
from insight_desk.acquisition.models import ArticleCandidate
from insight_desk.core import FailureKind
from insight_desk.semantic.facts import FactDraft, FactExtractionRequest
from insight_desk.semantic.fallback_extractors import SequentialFactExtractor


@dataclass
class DiscoveryRoute:
    route_id: str
    result: tuple[ArticleCandidate, ...] = ()
    error: bool = False

    def search(
        self,
        query: str,
        *,
        topic_id: str,
        limit: int = 10,
    ) -> tuple[ArticleCandidate, ...]:
        del query, topic_id, limit
        if self.error:
            raise DiscoveryError(FailureKind.TRANSIENT_PROVIDER, "synthetic")
        return self.result


@dataclass
class FactRoute:
    extractor_id: str
    result: tuple[FactDraft, ...] = ()

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        del request
        return self.result


class ToolObservabilityTests(unittest.TestCase):
    def test_discovery_composite_exposes_route_calls_errors_empty_and_selected(self) -> None:
        first = DiscoveryRoute("naver_search", error=True)
        second = DiscoveryRoute("bing_news_rss", result=())
        sentinel = ArticleCandidate(
            candidate_id="article:obs",
            url="https://example.com/obs",
            search_title="한화 관측 테스트",
            source_name="example.com",
            published_at=datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc),
            topic_ids=("kbo_hanwha",),
            query="한화",
            retrieved_via="gdelt_doc",
        )
        third = DiscoveryRoute("gdelt_doc", result=(sentinel,))
        discovery = SequentialNewsDiscovery((first, second, third))

        self.assertEqual(discovery.search("한화", topic_id="kbo_hanwha"), (sentinel,))
        stats = discovery.route_stats
        self.assertEqual(stats["naver_search"]["calls"], 1)
        self.assertEqual(stats["naver_search"]["errors"], 1)
        self.assertEqual(stats["bing_news_rss"]["calls"], 1)
        self.assertEqual(stats["bing_news_rss"]["empty"], 1)
        self.assertEqual(stats["gdelt_doc"]["calls"], 1)
        self.assertEqual(stats["gdelt_doc"]["selected"], 1)
        self.assertEqual(stats["gdelt_doc"]["candidates"], 1)
        self.assertEqual(stats["gdelt_doc"]["contributed"], 1)

    def test_fact_composite_exposes_route_calls_empty_and_selected(self) -> None:
        draft = FactDraft(
            draft_id="draft:obs",
            subject="한화",
            action="승리했다",
            object=None,
            evidence_ids=("ev:obs",),
        )
        first = FactRoute("kiwi", ())
        second = FactRoute("pecab", (draft,))
        third = FactRoute("surface", ())
        extractor = SequentialFactExtractor((first, second, third))
        # Route stats are initialized independently of request content; a tiny stand-in is enough
        # because the synthetic routes do not inspect it.
        result = extractor.extract(object())  # type: ignore[arg-type]
        self.assertEqual(result, (draft,))
        stats = extractor.route_stats
        self.assertEqual(stats["kiwi"]["calls"], 1)
        self.assertEqual(stats["kiwi"]["empty"], 1)
        self.assertEqual(stats["pecab"]["calls"], 1)
        self.assertEqual(stats["pecab"]["selected"], 1)
        self.assertEqual(stats["surface"]["calls"], 0)

    def test_production_audit_contains_non_sensitive_tool_usage_breakdown(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn('"tool_usage": tool_usage', source)
        self.assertIn('"discovery": discovery.route_stats', source)
        self.assertIn('"fact_extraction": extractor.route_stats', source)
        self.assertIn('"acquisition": acquisition_stats', source)
        self.assertIn('"generation": generation_route_stats', source)
        self.assertIn('"verification": verification_stats', source)
        self.assertIn('"identity": identity_stats', source)
        self.assertNotIn('"article_body":', source)
        self.assertNotIn('"claim_text":', source)


if __name__ == "__main__":
    unittest.main()
