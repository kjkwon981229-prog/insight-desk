from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from insight_desk.production_replay_v2 import run_recorded_production_replay


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase5_real_source_replay_v1.json"


class Phase5RealProductionReplayTests(unittest.TestCase):
    def test_historical_exact_source_bytes_replay_through_actual_v2_production(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["phase5_status"], "PARTIAL")
        self.assertFalse(fixture["raw_article_body_complete"])
        self.assertEqual(fixture["source_artifact"]["workflow_run_number"], 413)
        self.assertEqual(
            fixture["source_artifact"]["artifact_sha256"],
            "c7da6fe0b0b8f5356c3cb769f84c2db17e5dea81a9ffa932fa382709f941da64",
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = run_recorded_production_replay(
                fixture_path=FIXTURE,
                work_dir=Path(tmp),
            )

            self.assertTrue(result.state["publish"])
            self.assertEqual(result.state["published_entries"], 2)
            self.assertEqual(result.report["status"], "PARTIAL")
            self.assertFalse(result.report["raw_article_body_complete"])
            self.assertEqual(result.report["candidate_count"], 3)
            self.assertEqual(result.report["published_entries"], 2)
            self.assertEqual(result.report["network_calls"], 0)
            self.assertEqual(
                result.report["provider_mode"],
                "recorded_external_edges_real_production_pipeline",
            )
            self.assertTrue(result.report["canonical_bundle_validated"])
            self.assertGreaterEqual(result.report["canonical_parent_events"], 1)
            self.assertGreaterEqual(result.report["identity_same_event"], 1)
            self.assertTrue(result.report["pwa_state_audit_digest_bound"])

            manifest = result.publication_manifest
            self.assertEqual(manifest["version"], 2)
            self.assertEqual(len(manifest["publications"]), 2)
            by_topic = {item["topic"]: item for item in manifest["publications"]}
            self.assertEqual(set(by_topic), {"economy", "kbo_hanwha"})

            economy = by_topic["economy"]
            self.assertTrue(str(economy["parent_event_id"]).startswith("canonical-parent:bok_mpc:"))
            self.assertEqual(
                economy["primary_source_url"],
                "https://news.kbs.co.kr/news/pc/view/view.do?ncd=8647231&ref=A",
            )
            self.assertIsNone(by_topic["kbo_hanwha"]["parent_event_id"])
            self.assertEqual(
                by_topic["kbo_hanwha"]["primary_source_url"],
                "http://www.osen.co.kr/article/G1112864347",
            )

            self.assertEqual(result.state["publication_digest"], result.publication_digest)
            self.assertEqual(
                result.audit["publication_identity"]["sha256"],
                result.publication_digest,
            )
            self.assertEqual(
                result.state["publication_ids"],
                [item["publication_id"] for item in manifest["publications"]],
            )
            report_path = Path(tmp) / "replay-report.json"
            self.assertTrue(report_path.is_file())
            on_disk_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk_report["publication_digest"], result.publication_digest)

    def test_replay_harness_calls_public_production_entrypoint_not_helper_clone(self) -> None:
        source = (ROOT / "insight_desk" / "production_replay_v2.py").read_text(encoding="utf-8")
        self.assertIn("production.run_production(", source)
        self.assertNotIn("_core.run_production(", source)
        self.assertNotIn("evaluate_story_admission(", source)
        self.assertNotIn("visible_event_redundant(", source)
        self.assertNotIn("assess_material_event(", source)
        self.assertNotIn("resolve_candidate_pair(", source)

    def test_replay_fixture_preserves_real_urls_and_exact_source_provenance(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        urls = {case["source_url"] for case in fixture["cases"]}
        self.assertEqual(
            urls,
            {
                "https://news.kbs.co.kr/news/pc/view/view.do?ncd=8647231&ref=A",
                "https://www.kmib.co.kr/article/view.asp?arcid=9000006575&cp=nv",
                "http://www.osen.co.kr/article/G1112864347",
            },
        )
        for case in fixture["cases"]:
            self.assertIn("test_phase12", case["source_excerpt_provenance"])
            self.assertTrue(case["source_excerpt"].strip())
            self.assertTrue(case["historical_visible"]["headline"].strip())
            self.assertTrue(case["historical_visible"]["summary"].strip())


if __name__ == "__main__":
    unittest.main()
