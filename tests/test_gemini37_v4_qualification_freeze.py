from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini37FlashV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_v4_transient_block_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_37_flash_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-3.7-flash")
        self.assertEqual(record["status"], "QUALIFICATION_BLOCKED_TRANSIENT")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33146748912)
        self.assertEqual(
            record["head_sha"],
            "8ab2357d0b54e888eb54b85888b6ce10548043e9",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "PROVIDER_TRANSIENT_FAILURE")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": ["provider_transport:transient_provider"],
                "run413-bok-kmib-outlook-child": ["provider_transport:transient_provider"],
                "run413-kpop-alphadriveone-actor-preserved": [
                    "provider_transport:rate_limited",
                    "http_status:429",
                ],
                "run413-kbo-osen-same-game-source": [
                    "provider_transport:rate_limited",
                    "http_status:429",
                ],
            },
        )
        self.assertEqual(record["artifact_id"], 9676236791)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:0e8e02252ae70aac9a43296a8b2158ce821d1d843343a825e37315f5ba3dc756",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:8976ea03ca8fef3f198d8cbdcc20ac72b333b59361cace25a877b48bfdafb14d",
        )

        stale = payload["providers"]["gemini_37_flash"]
        self.assertEqual(stale["qualification_protocol"], 3)
        self.assertEqual(stale["run_id"], 33111216988)

        self.assertEqual(payload["active_qualification_protocol"], 4)
        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v4-provider-candidate-gemini37-flash", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-3.7-flash]", workflow)
        self.assertNotIn("qualify_gemini37_flash_v4", workflow)
        self.assertNotIn("event-understanding-gemini37-flash-v4", workflow)


if __name__ == "__main__":
    unittest.main()
