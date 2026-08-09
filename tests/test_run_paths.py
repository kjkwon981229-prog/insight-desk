from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from insight_desk.collectors.naver import NaverApiError, NaverCredentials
from insight_desk.config import load_topics
from insight_desk.domain.models import KeywordGroup, RunStatus
from insight_desk.run import execute


class ScenarioClient:
    def __init__(self, *, news_ok: bool, trend_ok: bool, secret: bool = False) -> None:
        self.news_ok = news_ok
        self.trend_ok = trend_ok
        if secret:
            self.credentials = NaverCredentials("id-that-must-not-leak", "secret-that-must-not-leak")

    def search_news(self, query: str, *, display: int = 100, start: int = 1):
        if not self.news_ok:
            raise NaverApiError("NETWORK", "news unavailable")
        return {
            "items": [
                {
                    "title": "결정론적 테스트 뉴스",
                    "description": "테스트용 요약",
                    "originallink": "https://example.com/story",
                    "link": "https://n.news.naver.com/story",
                    "pubDate": "Sun, 09 Aug 2026 08:00:00 +0900",
                }
            ]
        }

    def search_trend(self, groups: list[KeywordGroup], *, start_date: date, end_date: date, time_unit="date"):
        if not self.trend_ok:
            raise NaverApiError("NETWORK", "trend unavailable")
        first = groups[0]
        return "test-batch", {"results": [{"title": first.name, "data": [{"period": "2026-08-08", "ratio": 10}, {"period": "2026-08-09", "ratio": 20}]}]}


class RunPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="insight-desk-run-"))
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.config = Path("config/topics.json").resolve()

    def run_case(self, client: ScenarioClient):
        return execute(
            config_path=self.config,
            output_dir=self.root / "site",
            state_path=self.root / "state.json",
            cache_path=self.root / "cache.json",
            now=datetime.fromisoformat("2026-08-09T08:00:00+09:00"),
            client=client,
        )

    def test_news_only_is_published(self) -> None:
        state = self.run_case(ScenarioClient(news_ok=True, trend_ok=False))
        self.assertEqual(state.status, RunStatus.NEWS_ONLY)
        self.assertTrue(state.publish)
        self.assertTrue((self.root / "site/index.html").exists())

    def test_trends_only_is_published(self) -> None:
        state = self.run_case(ScenarioClient(news_ok=False, trend_ok=True))
        self.assertEqual(state.status, RunStatus.TRENDS_ONLY)
        self.assertTrue(state.publish)

    def test_total_failure_does_not_replace_existing_site(self) -> None:
        first = self.run_case(ScenarioClient(news_ok=True, trend_ok=True))
        self.assertEqual(first.status, RunStatus.COMPLETE)
        index = self.root / "site/index.html"
        before = index.read_bytes()
        second = self.run_case(ScenarioClient(news_ok=False, trend_ok=False))
        self.assertEqual(second.status, RunStatus.TOTAL_FAILURE)
        self.assertFalse(second.publish)
        self.assertEqual(index.read_bytes(), before)

    def test_secret_in_generated_data_blocks_publish(self) -> None:
        class LeakyClient(ScenarioClient):
            def search_news(self, query: str, *, display: int = 100, start: int = 1):
                payload = super().search_news(query, display=display, start=start)
                payload["items"][0]["title"] = "secret-that-must-not-leak"
                return payload

        state = self.run_case(LeakyClient(news_ok=True, trend_ok=True, secret=True))
        self.assertEqual(state.status, RunStatus.VALIDATION_FAILURE)
        self.assertFalse(state.publish)

