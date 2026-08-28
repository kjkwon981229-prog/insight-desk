from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class CerebrasGemma4_31BV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_zero_cost_access_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["cerebras_gemma4_31b_v4"]

        self.assertEqual(record["provider"], "cerebras")
        self.assertEqual(record["model"], "gemma-4-31b")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33168432708)
        self.assertEqual(
            record["head_sha"],
            "23b4a8ad72d78dd61f6d8cfec2a9f9555ad8be48",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "ZERO_COST_ACCESS_UNAVAILABLE")
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": [
                    "provider_transport:invalid_output",
                    "http_status:402",
                ],
                "run413-bok-kmib-outlook-child": [
                    "provider_transport:invalid_output",
                    "http_status:402",
                ],
                "run413-kpop-alphadriveone-actor-preserved": [
                    "provider_transport:invalid_output",
                    "http_status:402",
                ],
                "run413-kbo-osen-same-game-source": [
                    "provider_transport:invalid_output",
                    "http_status:402",
                ],
            },
        )
        self.assertEqual(record["artifact_id"], 9684571773)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:ab7e560d7370819fd9ff2ba0387b071bfa9158682342b7db474b61c145a88979",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:8fdd84a04d8061c999e58d3019d1ec54c5c2657875bd9b9f7ddd979d6ae2e434",
        )

        self.assertEqual(payload["active_qualification_protocol"], 4)
        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "  semantic-v4-provider-candidate-cerebras-gemma4-31b:\n",
            workflow,
        )
        self.assertNotIn("[semantic-v4-candidate:cerebras-gemma4-31b]", workflow)
        self.assertNotIn("qualify_cerebras_gemma4_31b_v4", workflow)
        self.assertNotIn("event-understanding-cerebras-gemma4-31b-v4", workflow)


if __name__ == "__main__":
    unittest.main()
