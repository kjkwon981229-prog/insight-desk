from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.acquisition.discovery import (
    AggregatedNewsDiscovery,
    BingNewsRssDiscovery,
    DiscoveryError,
    GdeltDocDiscovery,
    SequentialNewsDiscovery,
    default_news_discovery,
)
from insight_desk.acquisition.models import ArticleCandidate
from insight_desk.core import FailureKind


class Response:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


@dataclass
class Route:
    route_id: str
    result: tuple[ArticleCandidate, ...] = ()
    error: DiscoveryError | None = None
    calls: int = 0

    def search(self, query: str, *, topic_id: str, limit: int = 10) -> tuple[ArticleCandidate, ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def candidate(route: str, *, suffix: str | None = None, url: str | None = None) -> ArticleCandidate:
    suffix = suffix or route
    return ArticleCandidate(
        candidate_id=f"article-{route}-{suffix}",
        url=url or f"https://example.com/{suffix}",
        search_title=f"테스트 기사 {suffix}",
        source_name="example.com",
        published_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        topic_ids=("ai_tech",),
        query="테스트",
        retrieved_via=route,
    )


class Phase12BDiscoveryResilienceTests(unittest.TestCase):
    def test_aggregation_keeps_other_routes_after_error_or_empty(self) -> None:
        first = Route(
            "naver_search",
            error=DiscoveryError(FailureKind.TRANSIENT_PROVIDER, "quota"),
        )
        second = Route("bing_news_rss", result=())
        third = Route("gdelt_doc", result=(candidate("gdelt_doc"),))
        discovery = AggregatedNewsDiscovery((first, second, third))

        result = discovery.search("테스트", topic_id="ai_tech")

        self.assertEqual(result[0].retrieved_via, "gdelt_doc")
        self.assertEqual((first.calls, second.calls, third.calls), (1, 1, 1))
        self.assertEqual(discovery.route_stats["naver_search"]["errors"], 1)
        self.assertEqual(discovery.route_stats["gdelt_doc"]["contributed"], 1)

    def test_all_healthy_routes_contribute_even_when_naver_is_nonempty(self) -> None:
        first = Route("naver_search", result=(candidate("naver_search", suffix="n1"),))
        second = Route("bing_news_rss", result=(candidate("bing_news_rss", suffix="b1"),))
        third = Route("gdelt_doc", result=(candidate("gdelt_doc", suffix="g1"),))
        discovery = AggregatedNewsDiscovery((first, second, third))

        result = discovery.search("테스트", topic_id="ai_tech")

        self.assertEqual(
            tuple(item.retrieved_via for item in result),
            ("naver_search", "bing_news_rss", "gdelt_doc"),
        )
        self.assertEqual((first.calls, second.calls, third.calls), (1, 1, 1))
        for route_id in ("naver_search", "bing_news_rss", "gdelt_doc"):
            self.assertEqual(discovery.route_stats[route_id]["selected"], 1)
            self.assertEqual(discovery.route_stats[route_id]["contributed"], 1)

    def test_round_robin_prevents_first_route_from_monopolizing_limit(self) -> None:
        naver = Route(
            "naver_search",
            result=tuple(candidate("naver_search", suffix=f"n{i}") for i in range(1, 6)),
        )
        bing = Route(
            "bing_news_rss",
            result=tuple(candidate("bing_news_rss", suffix=f"b{i}") for i in range(1, 4)),
        )
        gdelt = Route(
            "gdelt_doc",
            result=tuple(candidate("gdelt_doc", suffix=f"g{i}") for i in range(1, 4)),
        )
        discovery = AggregatedNewsDiscovery((naver, bing, gdelt))

        result = discovery.search("테스트", topic_id="ai_tech", limit=5)

        self.assertEqual(
            tuple(item.retrieved_via for item in result),
            ("naver_search", "bing_news_rss", "gdelt_doc", "naver_search", "bing_news_rss"),
        )
        self.assertEqual(len(result), 5)
        self.assertEqual(discovery.route_stats["naver_search"]["contributed"], 2)
        self.assertEqual(discovery.route_stats["bing_news_rss"]["contributed"], 2)
        self.assertEqual(discovery.route_stats["gdelt_doc"]["contributed"], 1)

    def test_cross_provider_duplicate_url_is_mechanically_deduped_and_priority_route_wins(self) -> None:
        shared_naver = candidate(
            "naver_search",
            suffix="shared-n",
            url="HTTPS://News.Example.com:443/article?id=7#naver",
        )
        shared_bing = candidate(
            "bing_news_rss",
            suffix="shared-b",
            url="https://news.example.com/article?id=7#bing",
        )
        unique_bing = candidate("bing_news_rss", suffix="b2")
        discovery = AggregatedNewsDiscovery(
            (
                Route("naver_search", result=(shared_naver,)),
                Route("bing_news_rss", result=(shared_bing, unique_bing)),
            )
        )

        result = discovery.search("테스트", topic_id="ai_tech", limit=10)

        self.assertEqual(len(result), 2)
        self.assertIs(result[0], shared_naver)
        self.assertIs(result[1], unique_bing)
        self.assertEqual(discovery.route_stats["naver_search"]["contributed"], 1)
        self.assertEqual(discovery.route_stats["bing_news_rss"]["candidates"], 2)
        self.assertEqual(discovery.route_stats["bing_news_rss"]["contributed"], 1)

    def test_duplicate_headline_with_different_urls_is_not_discovery_deduped(self) -> None:
        left = candidate("naver_search", suffix="left", url="https://a.example.com/story")
        right = candidate("bing_news_rss", suffix="right", url="https://b.example.com/story")
        # Discovery owns URL/source candidate collection, not same-event meaning.
        left = ArticleCandidate(
            candidate_id=left.candidate_id,
            url=left.url,
            search_title="동일한 제목",
            source_name=left.source_name,
            published_at=left.published_at,
            topic_ids=left.topic_ids,
            query=left.query,
            retrieved_via=left.retrieved_via,
        )
        right = ArticleCandidate(
            candidate_id=right.candidate_id,
            url=right.url,
            search_title="동일한 제목",
            source_name=right.source_name,
            published_at=right.published_at,
            topic_ids=right.topic_ids,
            query=right.query,
            retrieved_via=right.retrieved_via,
        )
        discovery = AggregatedNewsDiscovery(
            (
                Route("naver_search", result=(left,)),
                Route("bing_news_rss", result=(right,)),
            )
        )
        self.assertEqual(len(discovery.search("테스트", topic_id="ai_tech")), 2)

    def test_all_failed_or_empty_preserves_fail_soft_error_contract(self) -> None:
        first = Route(
            "naver_search",
            error=DiscoveryError(FailureKind.TRANSIENT_PROVIDER, "naver unavailable"),
        )
        second = Route("bing_news_rss", result=())
        discovery = AggregatedNewsDiscovery((first, second))
        with self.assertRaises(DiscoveryError):
            discovery.search("테스트", topic_id="ai_tech")

    def test_sequential_name_is_compatibility_alias_for_aggregated_owner(self) -> None:
        self.assertIs(SequentialNewsDiscovery, AggregatedNewsDiscovery)

    def test_bing_redirect_url_is_resolved_to_publisher(self) -> None:
        encoded = "https%3A%2F%2Fnews.example.com%2Farticle%3Fx%3D1"
        value = f"https://www.bing.com/news/apiclick.aspx?url={encoded}&ref=RSS"
        self.assertEqual(
            BingNewsRssDiscovery._publisher_url(value),
            "https://news.example.com/article?x=1",
        )

    def test_gdelt_json_normalizes_to_article_candidate(self) -> None:
        payload = {
            "articles": [
                {
                    "url": "https://news.example.com/gdelt",
                    "title": "AI 테스트 기사",
                    "domain": "news.example.com",
                    "seendate": "20260823T120000Z",
                }
            ]
        }
        route = GdeltDocDiscovery(
            opener=lambda request, timeout: Response(json.dumps(payload).encode("utf-8"))
        )

        result = route.search("AI", topic_id="ai_tech")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].retrieved_via, "gdelt_doc")
        self.assertEqual(result[0].source_name, "news.example.com")
        self.assertIsNotNone(result[0].published_at)

    def test_default_discovery_has_three_routes_when_naver_is_configured(self) -> None:
        discovery = default_news_discovery(
            env={"NCP_CLIENT_ID": "id", "NCP_CLIENT_SECRET": "secret"}
        )
        self.assertIsInstance(discovery, AggregatedNewsDiscovery)
        self.assertEqual(
            tuple(route.route_id for route in discovery.routes),
            ("naver_search", "bing_news_rss", "gdelt_doc"),
        )

    def test_default_discovery_remains_operational_without_naver_credentials(self) -> None:
        discovery = default_news_discovery(env={})
        self.assertEqual(
            tuple(route.route_id for route in discovery.routes),
            ("bing_news_rss", "gdelt_doc"),
        )

    def test_production_uses_discovery_router_instead_of_direct_naver_search(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn("default_news_discovery", source)
        self.assertIn("discovery.search(", source)
        self.assertNotIn("naver.search_news(", source)


if __name__ == "__main__":
    unittest.main()
