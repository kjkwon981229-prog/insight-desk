from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts.qualify_event_understanding_provider import _source_from_case


class EventUnderstandingQualificationSourceTimeV2Tests(unittest.TestCase):
    def test_replay_clock_is_fetch_context_not_original_publication_time(self) -> None:
        replay_clock = datetime(2026, 8, 26, 18, 1, 16, tzinfo=timezone.utc)
        source = _source_from_case(
            {
                "case_id": "historical-proxy-time",
                "candidate_id": "candidate:historical-proxy-time",
                "source_name": "example-news",
                "source_url": "https://example.com/historical-proxy-time",
                "search_title": "기사 제목",
                "source_excerpt": "기사 본문에는 원 게시시각이 보존되어 있지 않다.",
            },
            replay_clock,
        )
        self.assertEqual(source.fetched_at, replay_clock)
        self.assertIsNone(source.publication_time)


if __name__ == "__main__":
    unittest.main()
