from __future__ import annotations

import unittest

from insight_desk.curation.config import CurationConfig
from insight_desk.curation.selection import Scored, select_daily


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.cfg = CurationConfig(pass_score=7.0, max_daily=5, max_per_topic=2)

    def test_topic_cap_third_dropped(self):
        candidates = [
            Scored(key=f"e{i}", topic_id="t1", topic_priority=1, total=8.0)
            for i in range(3)
        ]
        res = select_daily(candidates, cfg=self.cfg)
        self.assertEqual(len(res.selected), 2)
        self.assertEqual(len(res.dropped), 1)
        self.assertEqual(res.dropped[0][1], "topic_cap")

    def test_daily_cap_sixth_dropped(self):
        candidates = [
            Scored(key=f"e{i}", topic_id=f"t{i}", topic_priority=1, total=8.0)
            for i in range(6)
        ]
        res = select_daily(candidates, cfg=self.cfg)
        self.assertEqual(len(res.selected), 5)
        self.assertEqual(len(res.dropped), 1)
        self.assertEqual(res.dropped[0][1], "daily_cap")

    def test_below_pass_score_dropped(self):
        candidates = [
            Scored(key="e1", topic_id="t1", topic_priority=1, total=6.5),
        ]
        res = select_daily(candidates, cfg=self.cfg)
        self.assertEqual(len(res.selected), 0)
        self.assertEqual(res.dropped[0][1], "below_pass_score")

    def test_deterministic_sort(self):
        candidates = [
            Scored(key="b", topic_id="t1", topic_priority=2, total=8.0),
            Scored(key="a", topic_id="t2", topic_priority=2, total=8.0),
            Scored(key="c", topic_id="t3", topic_priority=3, total=8.0),
        ]
        res = select_daily(candidates, cfg=self.cfg)
        keys = [s.key for s in res.selected]
        self.assertEqual(keys, ["c", "a", "b"])

    def test_duplicate_key_ignored(self):
        candidates = [
            Scored(key="e1", topic_id="t1", topic_priority=1, total=8.0),
            Scored(key="e1", topic_id="t1", topic_priority=1, total=9.0),
        ]
        res = select_daily(candidates, cfg=self.cfg)
        self.assertEqual(len(res.selected), 1)
        self.assertEqual(res.selected[0].total, 8.0)


if __name__ == "__main__":
    unittest.main()
