from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import (
    AWAITING_PROVIDER_QUALIFICATION,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    load_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class MistralSmall4V5QualificationFreezeTests(unittest.TestCase):
    def test_exact_v5_mixed_failure_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["mistral_small4_v5"]

        self.assertEqual(record["provider"], "mistral")
        self.assertEqual(record["model"], "mistral-small-2603")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33229239969)
        self.assertEqual(
            record["head_sha"],
            "02e023f4c55902c5a8d40e6d6a0930ab12ada9e9",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 1)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_ADAPTER_AND_SEMANTIC_FAILURE",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": [
                    "status",
                    "primary_direct_min",
                    "expected_event_match",
                ],
                "run413-bok-kmib-outlook-child": [
                    "adapter_contract:adapter_output_contract"
                ],
                "run413-kbo-osen-same-game-source": [
                    "adapter_contract:adapter_output_contract"
                ],
            },
        )
        self.assertEqual(record["artifact_id"], 9707938165)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:7612efac4f5105f0b349bb1dbfdcd8a5faaeb841e6b95f470621e3ab12a500e6",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:5d839980e468769da18610bddd2f680cdef48d65ed1bc92aeaf7b15fa2b8be58",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(
            payload["qualification_contract_status"],
            AWAITING_PROVIDER_QUALIFICATION,
        )
        self.assertEqual(payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("  semantic-v5-provider-candidate-mistral-small4:\n", workflow)
        self.assertNotIn("[semantic-v5-candidate:mistral-small-2603]", workflow)
        self.assertNotIn("qualify_mistral_small4_v5", workflow)
        self.assertNotIn("event-understanding-v5-mistral-small4-candidate", workflow)


if __name__ == "__main__":
    unittest.main()
