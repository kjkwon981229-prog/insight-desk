from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import (
    CANDIDATE_QUALIFICATION_BLOCKED,
    NOT_QUALIFIED,
    load_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class OpenRouterLFM2526BV5QualificationFreezeTests(unittest.TestCase):
    def test_exact_not_qualified_result_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["openrouter_lfm25_26b_v5"]

        self.assertEqual(record["provider"], "openrouter")
        self.assertEqual(record["model"], "liquid/lfm-2.5-2.6b:free")
        self.assertEqual(record["status"], NOT_QUALIFIED)
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33235012040)
        self.assertEqual(
            record["head_sha"],
            "6c30921b4ec9a33729f3049ace216376c3651c5f",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 1)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_SEMANTIC_AND_INVALID_OUTPUT",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kmib-outlook-child": [
                    "event_drafts_min",
                    "expected_event_match",
                    "parent_hint_min",
                ],
                "run413-kpop-alphadriveone-actor-preserved": ["expected_event_match"],
                "run413-kbo-osen-same-game-source": ["provider_transport:invalid_output"],
            },
        )
        self.assertEqual(record["artifact_id"], 9709657693)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:b518f05f8a79ac0138a84291241b79736867a45bb631d351c3a966400a1f48dc",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:64817b024f235a0e50e6a69f6730bbe3a4199b64b8fa5d7913514072c167ac3a",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["provider_inventory_status"], CANDIDATE_QUALIFICATION_BLOCKED)
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertFalse(payload["full_production_correctness_claimed"])

    def test_consumed_one_shot_lane_is_absent(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v5-provider-candidate-openrouter-lfm25-26b", workflow)
        self.assertNotIn("[semantic-v5-candidate:openrouter-lfm25-26b]", workflow)
        self.assertNotIn("qualify_openrouter_lfm25_26b_v5", workflow)
        self.assertNotIn("event-understanding-v5-openrouter-lfm25-26b-candidate", workflow)


if __name__ == "__main__":
    unittest.main()
