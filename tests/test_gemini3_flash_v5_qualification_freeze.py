from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini3FlashV5QualificationFreezeTests(unittest.TestCase):
    def test_exact_v5_result_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_3_flash_v5"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-3-flash-preview")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33231176013)
        self.assertEqual(
            record["head_sha"],
            "11af67fe1f30954db53c1f0c772e48887fef37e4",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 2)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_CHILD_EVENT_AND_EVIDENCE_CONTRACT_FAILURE",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kmib-outlook-child": [
                    "event_drafts_min",
                    "expected_event_match",
                    "parent_hint_min",
                ],
                "run413-kpop-alphadriveone-actor-preserved": [
                    "adapter_contract:evidence_contract"
                ],
            },
        )
        self.assertEqual(record["artifact_id"], 9708548294)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:06ca070f3a35001d4e4ccb4e15bed39bebcc281e4b470b705641087880712e39",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:c498b45b22198f3e0ebddaa2e76a66799b366fab9c625ed750f6349185881fce",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertEqual(payload["provider_inventory_status"], "NO_ELIGIBLE_EXISTING_PROVIDER")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertFalse(payload["full_production_correctness_claimed"])

    def test_consumed_one_shot_lane_is_absent(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v5-provider-candidate-gemini-3-flash", workflow)
        self.assertNotIn("[semantic-v5-candidate:gemini-3-flash-preview]", workflow)
        self.assertNotIn("qualify_gemini3_flash_v5", workflow)


if __name__ == "__main__":
    unittest.main()
