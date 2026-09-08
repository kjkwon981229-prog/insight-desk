from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini36FlashV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_v4_not_qualified_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_36_flash_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-3.6-flash")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33144497986)
        self.assertEqual(record["head_sha"], "30443380b53e30d0daff46b495fe944b6d2d195e")
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 3)
        self.assertEqual(record["failure_classification"], "CHILD_EVENT_SEMANTIC_FAILURE")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kmib-outlook-child": [
                    "event_drafts_min",
                    "expected_event_match",
                    "parent_hint_min",
                ]
            },
        )
        self.assertEqual(record["artifact_id"], 9675278580)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:5df26a3924ae3582026a221964a752bf94ca35c7c478ae490dbf09c79eb9990f",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:f5f56ab815e2bdb2c7c211a8b440455bb9656fc9faade9852006f5a15b31c21d",
        )
        self.assertLess(record["qualification_protocol"], payload["active_qualification_protocol"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v4-provider-candidate-gemini36-flash", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-3.6-flash]", workflow)
        self.assertNotIn("qualify_gemini36_flash_v4", workflow)
        self.assertNotIn("event-understanding-gemini36-flash-v4", workflow)


if __name__ == "__main__":
    unittest.main()
