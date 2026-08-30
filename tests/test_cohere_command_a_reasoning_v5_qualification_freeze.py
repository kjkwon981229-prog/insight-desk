from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class CohereCommandAReasoningV5QualificationFreezeTests(unittest.TestCase):
    def test_exact_v5_result_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["cohere_command_a_reasoning_v5"]

        self.assertEqual(record["provider"], "cohere")
        self.assertEqual(record["model"], "command-a-reasoning-08-2025")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33230437202)
        self.assertEqual(
            record["head_sha"],
            "f264f06083bd9c23f425339d3b45ac12119dd585",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 2)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_CHILD_EVENT_AND_EVENT_MATCH_SEMANTIC_FAILURE",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kmib-outlook-child": [
                    "event_drafts_min",
                    "expected_event_match",
                    "parent_hint_min",
                ],
                "run413-kbo-osen-same-game-source": ["expected_event_match"],
            },
        )
        self.assertEqual(record["artifact_id"], 9708318114)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:8d695b37197d52e94f17fd488d0bb9645dc8464398fc8e946216451272f5610e",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:e149d7fbd149e341c017a8ab96712a5f1032c60e15009348db69d915c8385d01",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertFalse(payload["full_production_correctness_claimed"])

    def test_consumed_one_shot_lane_is_absent(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v5-provider-candidate-cohere-command-a-reasoning", workflow)
        self.assertNotIn("[semantic-v5-candidate:command-a-reasoning-08-2025]", workflow)
        self.assertNotIn("qualify_cohere_command_a_reasoning_v5", workflow)


if __name__ == "__main__":
    unittest.main()
