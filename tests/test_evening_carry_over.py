from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from insight_desk.production_replay_v2 import run_recorded_production_replay

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase5_real_source_replay_v1.json"
_RUNTIME = importlib.util.find_spec("kiwipiepy") is not None


@unittest.skipUnless(_RUNTIME, "needs the same semantic runtime as production")
class EveningCarryOverTests(unittest.TestCase):
    def test_evening_shows_the_morning_items_again_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.json"
            morning = run_recorded_production_replay(
                fixture_path=FIXTURE, work_dir=root / "morning", history_out_path=history
            )
            morning_ids = list(morning.state["publication_ids"])
            self.assertEqual(len(morning_ids), 3)
            self.assertTrue(history.is_file())

            evening = run_recorded_production_replay(
                fixture_path=FIXTURE,
                work_dir=root / "evening",
                edition="evening",
                history_in_path=history,
                history_out_path=history,
            )
            evening_ids = list(evening.state["publication_ids"])
            self.assertEqual(evening.state["edition"], "evening")
            self.assertEqual(len(evening_ids), len(set(evening_ids)), "an item appeared twice")
            self.assertEqual(sorted(evening_ids), sorted(morning_ids))

            # The morning items stay remembered for the 7-day check after the evening run.
            saved = json.loads(history.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(saved["entries"]), 3)

    def test_a_second_morning_run_still_drops_items_already_shown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.json"
            first = run_recorded_production_replay(
                fixture_path=FIXTURE, work_dir=root / "first", history_out_path=history
            )
            second = run_recorded_production_replay(
                fixture_path=FIXTURE,
                work_dir=root / "second",
                history_in_path=history,
                history_out_path=history,
            )
            first_ids = set(first.state["publication_ids"])
            second_ids = set(second.state["publication_ids"])
            self.assertLess(len(second_ids), len(first_ids))
            self.assertFalse(first_ids & second_ids, "a morning run repeated an item already shown")
            self.assertEqual(second.audit["curation_stats"]["hard_filtered"].get("duplicate_7d"), 3)


if __name__ == "__main__":
    unittest.main()
