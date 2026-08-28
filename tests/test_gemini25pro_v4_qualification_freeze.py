from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini25ProV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_v4_provider_unavailable_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_25_pro_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-2.5-pro")
        self.assertEqual(record["status"], "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33152273374)
        self.assertEqual(
            record["head_sha"],
            "b02d7abc72cdda5302c8c24256ac0013e65b3a23",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": [
                    "provider_transport:invalid_output",
                    "http_status:404",
                ],
                "run413-bok-kmib-outlook-child": [
                    "provider_transport:invalid_output",
                    "http_status:404",
                ],
                "run413-kpop-alphadriveone-actor-preserved": [
                    "provider_transport:invalid_output",
                    "http_status:404",
                ],
                "run413-kbo-osen-same-game-source": [
                    "provider_transport:invalid_output",
                    "http_status:404",
                ],
            },
        )
        self.assertEqual(record["artifact_id"], 9678194163)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:29b1c06e25b229a27673ba56ee5f26c9f009214c72c66168e83c0171c7c397df",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:7607598c7b96ab6c76fd45b066339f3939a3e397de6671d274f8fb132a59d639",
        )

        self.assertEqual(payload["active_qualification_protocol"], 4)
        self.assertEqual(payload["provider_inventory_status"], "NO_ELIGIBLE_EXISTING_PROVIDER")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v4-provider-candidate-gemini25-pro", workflow)
        self.assertNotIn("phase12-eu-v4-gemini25pro", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-2.5-pro]", workflow)
        self.assertNotIn("qualify_gemini25_pro_v4", workflow)
        self.assertNotIn("event-understanding-gemini25-pro-v4", workflow)


if __name__ == "__main__":
    unittest.main()
