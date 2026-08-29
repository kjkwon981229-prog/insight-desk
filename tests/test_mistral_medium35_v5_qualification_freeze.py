from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import (
    AWAITING_PROVIDER_QUALIFICATION,
    CANDIDATE_QUALIFICATION_BLOCKED,
    load_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class MistralMedium35V5QualificationFreezeTests(unittest.TestCase):
    def test_exact_v5_semantic_failure_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["mistral_medium35_v5"]

        self.assertEqual(record["provider"], "mistral")
        self.assertEqual(record["model"], "mistral-medium-3-5")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33180474834)
        self.assertEqual(
            record["head_sha"],
            "3023001921a3b87c196d91bcf3dffb94dccaba46",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 3)
        self.assertEqual(record["failure_classification"], "EVENT_MATCH_SEMANTIC_FAILURE")
        self.assertEqual(
            record["case_failures"],
            {"run413-kbo-osen-same-game-source": ["expected_event_match"]},
        )
        self.assertEqual(record["artifact_id"], 9689501036)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:3f0af22349d62b36bc44ce4bf59471d3a635928e4b3f9bc3873183017640707c",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:ccd0f3685dbac6b863cf98276b3b44ec38eae8113b76627d05c3d52e251d3211",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(
            payload["qualification_contract_status"],
            AWAITING_PROVIDER_QUALIFICATION,
        )
        self.assertEqual(payload["provider_inventory_status"], CANDIDATE_QUALIFICATION_BLOCKED)
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("  semantic-v5-provider-candidate-mistral-medium35:\n", workflow)
        self.assertNotIn("[semantic-v5-candidate:mistral-medium-3-5]", workflow)
        self.assertNotIn("qualify_mistral_medium35_v5", workflow)
        self.assertNotIn("event-understanding-v5-mistral-medium35-candidate", workflow)


if __name__ == "__main__":
    unittest.main()
