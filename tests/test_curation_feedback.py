from __future__ import annotations

import json
import unittest
import urllib.error

from insight_desk.curation.config import CurationConfig
from insight_desk.curation.feedback import adjust_by_topic, fetch_feedback_summary

CFG = CurationConfig()
LABELS = {"AI 테크": "ai_tech", "경제": "economy"}


class _Response:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.raw


class FeedbackAdjustTests(unittest.TestCase):
    def test_good_adds_half_and_bad_subtracts_one(self) -> None:
        summary = {"topics": {"AI 테크": {"good": 1, "bad": 0}, "경제": {"good": 0, "bad": 1}}}
        result = adjust_by_topic(summary, LABELS, CFG)
        self.assertEqual(result, {"ai_tech": 0.5, "economy": -1.0})

    def test_totals_are_clamped_to_the_configured_range(self) -> None:
        summary = {"topics": {"AI 테크": {"good": 10, "bad": 0}, "경제": {"good": 0, "bad": 10}}}
        result = adjust_by_topic(summary, LABELS, CFG)
        self.assertEqual(result["ai_tech"], CFG.feedback_max)
        self.assertEqual(result["economy"], CFG.feedback_min)

    def test_unknown_labels_and_bad_shapes_are_ignored(self) -> None:
        self.assertEqual(adjust_by_topic({"topics": {"모르는 분야": {"good": 3, "bad": 0}}}, LABELS, CFG), {})
        self.assertEqual(adjust_by_topic({"topics": {"경제": {"good": "3", "bad": 0}}}, LABELS, CFG), {})
        self.assertEqual(adjust_by_topic({"topics": {"경제": {"good": -1, "bad": 0}}}, LABELS, CFG), {})
        self.assertEqual(adjust_by_topic({}, LABELS, CFG), {})


class FetchSummaryTests(unittest.TestCase):
    def test_reads_the_summary_endpoint(self) -> None:
        seen = []

        def opener(request, timeout):
            seen.append(request.full_url)
            return _Response(json.dumps({"ok": True, "topics": {}}).encode())

        self.assertEqual(fetch_feedback_summary("https://w.example/", opener=opener)["ok"], True)
        self.assertEqual(seen, ["https://w.example/feedback/summary"])

    def test_every_failure_means_no_feedback(self) -> None:
        def broken(request, timeout):
            raise urllib.error.URLError("down")

        self.assertEqual(fetch_feedback_summary("https://w.example", opener=broken), {})
        self.assertEqual(fetch_feedback_summary("https://w.example", opener=lambda r, timeout: _Response(b"nope")), {})
        self.assertEqual(fetch_feedback_summary(None), {})
        self.assertEqual(fetch_feedback_summary("http://insecure.example"), {})


if __name__ == "__main__":
    unittest.main()
