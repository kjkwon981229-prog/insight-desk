from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "tests" / "fixtures" / "phase5_replay_inventory_v1.json"
REAL_REPLAY = ROOT / "tests" / "fixtures" / "phase5_real_source_replay_v1.json"
PROXY_CORPUS = ROOT / "tests" / "fixtures" / "phase12_story_replay_corpus.json"
ACQUISITION_CANARY = ROOT / "benchmarks" / "acquisition" / "results" / "live-canary-2026-08-23.json"
PHASE10_CANARY = ROOT / "benchmarks" / "semantic" / "results" / "phase10-fresh-live-closure-2026-08-23.json"


class Phase5ReplayInventoryTests(unittest.TestCase):
    def test_inventory_matches_recoverable_exact_source_replay_fixture(self) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        replay = json.loads(REAL_REPLAY.read_text(encoding="utf-8"))

        self.assertEqual(inventory["status"], "PARTIAL_COMPLETE")
        self.assertFalse(inventory["full_raw_body_replay"]["available"])
        self.assertEqual(inventory["full_raw_body_replay"]["known_persisted_full_raw_articles"], 0)
        self.assertFalse(replay["raw_article_body_complete"])

        replay_case_ids = {case["case_id"] for case in replay["cases"]}
        inventory_case_ids = {
            case["case_id"]
            for case in inventory["exact_source_production_replay"]["cases"]
        }
        self.assertEqual(inventory_case_ids, replay_case_ids)
        self.assertEqual(
            inventory["exact_source_production_replay"]["candidate_count"],
            len(replay["cases"]),
        )
        self.assertEqual(
            inventory["exact_source_production_replay"]["expected_publication_count"],
            replay["expected"]["published_entries"],
        )
        self.assertTrue(
            all(
                case["evidence_class"] == "real_url_plus_exact_source_bytes"
                for case in inventory["exact_source_production_replay"]["cases"]
            )
        )

    def test_visible_proxy_corpus_is_explicitly_excluded_from_source_replay_denominator(self) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        corpus = json.loads(PROXY_CORPUS.read_text(encoding="utf-8"))
        proxy = inventory["historical_visible_proxy_corpus"]

        self.assertEqual(proxy["cards"], corpus["counts"]["cards"])
        self.assertEqual(proxy["pass_labels"], corpus["counts"]["pass"])
        self.assertEqual(proxy["p1_labels"], corpus["counts"]["p1"])
        self.assertEqual(proxy["admission_unresolved"], corpus["counts"]["admission_unresolved"])
        self.assertEqual(proxy["source_unresolved"], corpus["counts"]["source_unresolved"])
        self.assertIn("must not be reported as raw article replay", proxy["forbidden_use"])
        self.assertIn("omit raw article bodies", corpus["scope"]["raw_source_fact_limitation"])

    def test_historical_live_canary_records_prove_why_full_body_replay_is_unavailable(self) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        acquisition = json.loads(ACQUISITION_CANARY.read_text(encoding="utf-8"))
        phase10 = json.loads(PHASE10_CANARY.read_text(encoding="utf-8"))

        self.assertFalse(acquisition["privacy_and_safety"]["article_body_committed"])
        self.assertFalse(acquisition["privacy_and_safety"]["article_body_logged"])
        self.assertFalse(phase10["safety_and_cost"]["article_body_logged"])
        self.assertFalse(inventory["live_acquisition_canary"]["replayable_from_repo"])
        self.assertFalse(inventory["phase10_live_canary"]["replayable_from_repo"])


if __name__ == "__main__":
    unittest.main()
