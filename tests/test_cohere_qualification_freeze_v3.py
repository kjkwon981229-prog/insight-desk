from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class CohereQualificationFreezeV3Tests(unittest.TestCase):
    def test_cohere_v3_definitive_failure_is_frozen_exactly(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["cohere_command_a_plus"]
        self.assertEqual(record["provider"], "cohere")
        self.assertEqual(record["model"], "command-a-plus-05-2026")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["qualification_protocol"], 3)
        self.assertEqual(record["run_id"], 33104385499)
        self.assertEqual(
            record["head_sha"],
            "c3a7bc7bcd7f81b9f8f31ef14922950f7a49ea57",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "ADAPTER_OUTPUT_CONTRACT")
        for case_id in (
            "run413-bok-kbs-rate-decision",
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
            "run413-kbo-osen-same-game-source",
        ):
            self.assertEqual(
                record["case_failures"][case_id],
                ["adapter_contract:adapter_output_contract"],
            )
        self.assertEqual(record["artifact_id"], 9659910291)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:73594960aa92f046fef4e7ee151721b6d40ba09e064963f9d3f5ba619f567259",
        )

        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_cohere_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v3-provider-candidate-cohere-command-a-plus", workflow)
        self.assertNotIn("[semantic-v3-candidate:cohere-command-a-plus]", workflow)
        self.assertNotIn("COHERE_API_KEY", workflow)


if __name__ == "__main__":
    unittest.main()
