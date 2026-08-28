from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini35FlashV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_v4_not_qualified_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_35_flash_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-3.5-flash")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33141373191)
        self.assertEqual(
            record["head_sha"],
            "d81dd3cb5e51dda927176efbb2633ab7fbb73249",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 3)
        self.assertEqual(record["failure_classification"], "EVENT_DRAFT_CONTRACT")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": [
                    "adapter_contract:event_draft_contract"
                ]
            },
        )
        self.assertEqual(record["artifact_id"], 9674081915)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:db59c3f2db9e09a61dc3fbad22021ccde116ebb2394e05f14051acfbbbfa7386",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:0debab420e17a762c52b57db626b84db677c084b4659ee70e2f99054c25dcced",
        )

        self.assertEqual(payload["active_qualification_protocol"], 4)
        self.assertEqual(payload["provider_inventory_status"], "NO_ELIGIBLE_EXISTING_PROVIDER")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v4-provider-candidate-gemini35-flash", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-3.5-flash]", workflow)
        self.assertNotIn("qualify_gemini35_flash_v4", workflow)
        self.assertNotIn("event-understanding-gemini35-flash-v4", workflow)


if __name__ == "__main__":
    unittest.main()
