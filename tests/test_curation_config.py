from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from insight_desk.curation.config import CurationConfig, load_curation_config
from insight_desk.curation.selection import Scored, select_daily

KST = timezone(timedelta(hours=9))
REPO_ROOT = Path(__file__).resolve().parents[1]


class CurationConfigTests(unittest.TestCase):
    def test_shipped_config_loads_and_matches_defaults(self):
        shipped = load_curation_config(REPO_ROOT / "config" / "curation.json")
        default = CurationConfig()
        self.assertEqual(shipped, default)

    def test_missing_file_gives_defaults(self):
        self.assertEqual(load_curation_config(None), CurationConfig())
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_curation_config(Path(tmp) / "nope.json"), CurationConfig())

    def test_unknown_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"pass_scor": 7}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_curation_config(path)

    def test_hanwha_needs_a_higher_score(self):
        cfg = CurationConfig()
        self.assertEqual(cfg.pass_score_for("economy"), 7.0)
        self.assertEqual(cfg.pass_score_for("kbo_hanwha"), 8.0)
        pool = [
            Scored(key="h7", topic_id="kbo_hanwha", topic_priority=65, total=7.0),
            Scored(key="h8", topic_id="kbo_hanwha", topic_priority=65, total=8.0),
            Scored(key="e7", topic_id="economy", topic_priority=75, total=7.0),
        ]
        result = select_daily(pool, cfg=cfg)
        self.assertEqual([item.key for item in result.selected], ["h8", "e7"])
        self.assertEqual([(item.key, why) for item, why in result.dropped], [("h7", "below_pass_score")])


if __name__ == "__main__":
    unittest.main()
