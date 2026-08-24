from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import unittest

from insight_desk.acquisition import ArticleCandidate, SequentialNewsDiscovery
from insight_desk.acquisition.source_quality import (
    source_url_has_stale_embedded_date,
    with_stale_url_filter,
)
from scripts.validate_feed_artifact import _stale_source_url


def candidate(url: str, *, suffix: str) -> ArticleCandidate:
    return ArticleCandidate(
        candidate_id=f"article:{suffix}",
        url=url,
        search_title=f"기사 {suffix}",
        source_name="example.com",
        published_at=None,
        topic_ids=("ai_tech",),
        query="AI",
        retrieved_via="synthetic",
    )


@dataclass
class FakeRoute:
    route_id: str
    output: tuple[ArticleCandidate, ...]

    def search(
        self,
        query: str,
        *,
        topic_id: str,
        limit: int = 10,
    ) -> tuple[ArticleCandidate, ...]:
        del query, topic_id
        return self.output[:limit]


class Phase12KStaleSourcePreselectionTests(unittest.TestCase):
    def test_measured_old_compact_date_is_stale(self) -> None:
        self.assertTrue(
            source_url_has_stale_embedded_date(
                "https://example.com/news/20260327/story",
                today=date(2026, 8, 24),
            )
        )

    def test_recent_compact_date_remains_eligible(self) -> None:
        self.assertFalse(
            source_url_has_stale_embedded_date(
                "https://example.com/news/20260822/story",
                today=date(2026, 8, 24),
            )
        )

    def test_invalid_calendar_token_is_not_treated_as_a_date(self) -> None:
        self.assertFalse(
            source_url_has_stale_embedded_date(
                "https://example.com/news/20261340/story",
                today=date(2026, 8, 24),
            )
        )

    def test_discovery_falls_through_when_first_route_contains_only_stale_urls(self) -> None:
        stale = candidate("https://old.example.com/20200101/story", suffix="old")
        fresh = candidate("https://fresh.example.com/current/story", suffix="fresh")
        discovery = with_stale_url_filter(
            SequentialNewsDiscovery(
                (
                    FakeRoute("first", (stale,)),
                    FakeRoute("second", (fresh,)),
                )
            )
        )

        result = discovery.search("AI", topic_id="ai_tech", limit=10)

        self.assertEqual(result, (fresh,))
        stats = discovery.route_stats
        self.assertEqual(stats["first"]["empty"], 1)
        self.assertEqual(stats["first"]["selected"], 0)
        self.assertEqual(stats["second"]["selected"], 1)

    def test_preselection_and_final_validator_agree_on_conservative_backstop(self) -> None:
        stale_url = "https://example.com/archive/20200101/story"
        undated_url = "https://example.com/current/story"
        self.assertEqual(
            source_url_has_stale_embedded_date(stale_url),
            _stale_source_url(stale_url),
        )
        self.assertEqual(
            source_url_has_stale_embedded_date(undated_url),
            _stale_source_url(undated_url),
        )


if __name__ == "__main__":
    unittest.main()
