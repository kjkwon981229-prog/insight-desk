from __future__ import annotations

import unittest
import urllib.error
from pathlib import Path

from insight_desk.acquisition.discovery import DiscoveryError
from insight_desk.acquisition.feeds import FeedRssDiscovery
from scripts import phase11_daily_production as production

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Pitch design study</title><link>https://blogs.example.com/a</link><pubDate>Mon, 19 Oct 2026 01:00:00 GMT</pubDate></item>
<item><title>Duplicate</title><link>https://blogs.example.com/a</link></item>
<item><title>Bad link</title><link>ftp://blogs.example.com/b</link></item>
<item><title>No date</title><link>https://blogs.example.com/c</link></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom one</title><link rel="alternate" href="https://example.org/x"/><published>2026-10-18T09:00:00+09:00</published></entry>
</feed>"""


class _Response:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.raw[:limit] if limit > 0 else self.raw


class FeedRssDiscoveryTests(unittest.TestCase):
    def test_rss_items_become_candidates_without_duplicates_or_bad_links(self) -> None:
        feed = FeedRssDiscovery(opener=lambda request, timeout: _Response(RSS))
        found = feed.fetch("https://blogs.example.com/feed", topic_id="t", limit=10)
        self.assertEqual([c.url for c in found], ["https://blogs.example.com/a", "https://blogs.example.com/c"])
        self.assertIsNotNone(found[0].published_at)
        self.assertIsNone(found[1].published_at)
        self.assertEqual(found[0].topic_ids, ("t",))
        self.assertEqual(feed.route_stats["blogs.example.com"]["candidates"], 2)

    def test_atom_entries_are_read(self) -> None:
        feed = FeedRssDiscovery(opener=lambda request, timeout: _Response(ATOM))
        found = feed.fetch("https://example.org/atom", topic_id="t")
        self.assertEqual([c.search_title for c in found], ["Atom one"])
        self.assertIsNotNone(found[0].published_at)

    def test_network_and_xml_errors_are_discovery_errors(self) -> None:
        def broken(request, timeout):
            raise urllib.error.URLError("down")

        with self.assertRaises(DiscoveryError):
            FeedRssDiscovery(opener=broken).fetch("https://x.example/feed", topic_id="t")
        with self.assertRaises(DiscoveryError):
            FeedRssDiscovery(opener=lambda request, timeout: _Response(b"<html>")).fetch(
                "https://x.example/feed", topic_id="t"
            )

    def test_feed_lane_feeds_the_query_candidate_batches(self) -> None:
        core = production._core
        topic = core.TopicConfig(
            topic_id="t", name="n", priority=1, candidate_budget=5, selection_cap=1,
            intent_anchors=("a",), required_intent_terms=(), news_queries=(),
            feed_urls=("https://blogs.example.com/feed",),
        )
        feed = FeedRssDiscovery(opener=lambda request, timeout: _Response(RSS))

        class NoSearch:
            def search(self, *args, **kwargs):
                raise AssertionError("no query configured")

        attempts: list[dict] = []
        batches = list(core._query_candidate_batches(NoSearch(), topic, attempts, feed))
        self.assertEqual([q for q, _ in batches], ["feed:https://blogs.example.com/feed"] * 2)

    def test_topic_needs_queries_or_feeds_and_https_only(self) -> None:
        core = production._core
        base = dict(topic_id="t", name="n", priority=1, candidate_budget=5, selection_cap=1,
                    intent_anchors=("a",), required_intent_terms=())
        with self.assertRaises(ValueError):
            core.TopicConfig(news_queries=(), **base)
        with self.assertRaises(ValueError):
            core.TopicConfig(news_queries=(), feed_urls=("http://insecure.example/feed",), **base)


if __name__ == "__main__":
    unittest.main()
