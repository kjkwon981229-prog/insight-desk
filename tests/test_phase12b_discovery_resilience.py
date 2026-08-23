from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.acquisition.discovery import (
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


def candidate(route: str) -> ArticleCandidate:
    return ArticleCandidate(
        candidate_id=f"article-{route}",
        url=f"https://example.com/{route}",
        search_title="테스트 기사",
        source_name="example.com",
        published_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        topic_ids=("ai_tech",),
        query="테스트",
        retrieved_via=route,
    )


class Phase12BDiscoveryResilienceTests(unittest.TestCase):
    def test_sequential_discovery_uses_next_route_only_after_error_or_empty(self) -> None:
        first = Route(
            "naver_search",
            error=DiscoveryError(FailureKind.TRANSIENT_PROVIDER, "quota"),
        )
        second = Route("bing_news_rss", result=())
        third = Route("gdelt_doc", result=(candidate("gdelt_doc"),))
        discovery = SequentialNewsDiscovery((first, second, third))

        result = discovery.search("테스트", topic_id="ai_tech")

        self.assertEqual(result[0].retrieved_via, "gdelt_doc")
        self.assertEqual((first.calls, second.calls, third.calls), (1, 1, 1))

    def test_sequential_discovery_stops_after_first_healthy_nonempty_route(self) -> None:
        first = Route("naver_search", result=(candidate("naver_search"),))
        second = Route("bing_news_rss", result=(candidate("bing_news_rss"),))
        third = Route("gdelt_doc", result=(candidate("gdelt_doc"),))
        discovery = SequentialNewsDiscovery((first, second, third))

        result = discovery.search("테스트", topic_id="ai_tech")

        self.assertEqual(result[0].retrieved_via, "naver_search")
        self.assertEqual((first.calls, second.calls, third.calls), (1, 0, 0))

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
