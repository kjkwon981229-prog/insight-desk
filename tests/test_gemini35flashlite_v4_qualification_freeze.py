from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini35FlashLiteV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_v4_not_qualified_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_35_flash_lite_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-3.5-flash-lite")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33154997997)
        self.assertEqual(record["head_sha"], "9aae9e36c1358fc3693118d99c2bd9da796f8a4a")
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 1)
        self.assertEqual(record["failure_classification"], "EVENT_DRAFT_CONTRACT")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": ["adapter_contract:event_draft_contract"],
                "run413-bok-kmib-outlook-child": ["adapter_contract:event_draft_contract"],
                "run413-kbo-osen-same-game-source": ["adapter_contract:event_draft_contract"],
            },
        )
        self.assertEqual(record["artifact_id"], 9679252510)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:dbcf2e735404a3267f862dd90ebb1a9b5475e0c73994eb255bba2d247d43a6fc",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:73762b6e18f9d8c05c2ce7cf6575c2bff383907dacc6f02b78c8c6d160b44f0b",
        )
        self.assertLess(record["qualification_protocol"], payload["active_qualification_protocol"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("\n  semantic-v4-provider-candidate-gemini35-flash-lite:\n", workflow)
        self.assertNotIn("phase12-eu-v4-gemini35flashlite", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-3.5-flash-lite]", workflow)
        self.assertNotIn("qualify_gemini35_flash_lite_v4", workflow)
        self.assertNotIn("event-understanding-gemini35-flash-lite-v4", workflow)


if __name__ == "__main__":
    unittest.main()
