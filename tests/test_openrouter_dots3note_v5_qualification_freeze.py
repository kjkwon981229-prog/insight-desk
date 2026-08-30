from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class OpenRouterDots3NoteV5QualificationFreezeTests(unittest.TestCase):
    def test_exact_v5_result_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["openrouter_dots3note_v5"]

        self.assertEqual(record["provider"], "openrouter")
        self.assertEqual(record["model"], "dots-studio/dots-3-note-preview:free")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33232152925)
        self.assertEqual(
            record["head_sha"],
            "2e62c43167754f6598cb12b990bf2a0a17a34a35",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 2)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_INVALID_OUTPUT_AND_EVENT_MATCH_FAILURE",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kmib-outlook-child": ["provider_transport:invalid_output"],
                "run413-kbo-osen-same-game-source": ["expected_event_match"],
            },
        )
        self.assertEqual(record["artifact_id"], 9708845325)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:16536bedff717a665403581c4346a8ddfbae1caac87e0e69cb7d2bfc4f815729",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:ce6e0af6e8137c3762eb1d15826c3fd98d7a9512d0b2cf98b4a0a7d20b47bbbd",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertFalse(payload["full_production_correctness_claimed"])

    def test_consumed_one_shot_lane_is_absent(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v5-provider-candidate-openrouter-dots3-note", workflow)
        self.assertNotIn("[semantic-v5-candidate:openrouter-dots3-note-preview]", workflow)
        self.assertNotIn("qualify_openrouter_dots3note_v5", workflow)


if __name__ == "__main__":
    unittest.main()
