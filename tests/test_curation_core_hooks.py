from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import phase11_daily_production_core as core

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)


class CoreCurationHookTests(unittest.TestCase):
    def test_topics_json_negative_context_reaches_topic_config(self):
        topics = {topic.topic_id: topic for topic in core.load_topics(REPO_ROOT / "config" / "topics.json")}
        self.assertIn("광고", topics["ai_tech"].negative_context)
        self.assertEqual(topics["ai_tech"].freshness_days, 3)

    def test_freshness_days_is_read_from_topic_config(self):
        payload = {
            "topics": [
                {
                    "id": "analysis",
                    "name": "분석",
                    "enabled": True,
                    "priority": 1,
                    "candidate_budget": 4,
                    "selection_cap": 3,
                    "intent_anchors": ["분석"],
                    "news_queries": ["분석"],
                    "freshness_days": 30,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            (topic,) = core.load_topics(path)
        self.assertEqual(topic.freshness_days, 30)

    def test_is_fresh_default_window_is_72_hours(self):
        self.assertTrue(core._is_fresh(NOW - timedelta(hours=71), NOW))
        self.assertFalse(core._is_fresh(NOW - timedelta(hours=73), NOW))
        self.assertIsNone(core._is_fresh(None, NOW))

    def test_is_fresh_honours_longer_topic_window(self):
        published = NOW - timedelta(days=20)
        self.assertFalse(core._is_fresh(published, NOW))
        self.assertTrue(core._is_fresh(published, NOW, 30))
        self.assertFalse(core._is_fresh(NOW - timedelta(days=31), NOW, 30))

    def test_topic_config_rejects_non_positive_freshness(self):
        with self.assertRaises(ValueError):
            core.TopicConfig(
                topic_id="x", name="x", priority=1, candidate_budget=1, selection_cap=1,
                intent_anchors=("a",), required_intent_terms=(), news_queries=("a",),
                freshness_days=0,
            )

    def test_published_candidate_new_fields_are_optional(self):
        fields = core.PublishedCandidate.__dataclass_fields__
        for name in ("article_id", "article_title", "score"):
            self.assertIn(name, fields)
            self.assertIsNot(fields[name].default, dataclasses.MISSING)


if __name__ == "__main__":
    unittest.main()
