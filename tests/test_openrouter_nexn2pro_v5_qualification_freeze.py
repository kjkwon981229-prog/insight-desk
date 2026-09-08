from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import (
    CANDIDATE_QUALIFICATION_BLOCKED,
    QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE,
    load_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class OpenRouterNexN2ProV5QualificationFreezeTests(unittest.TestCase):
    def test_exact_provider_unavailable_result_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["openrouter_nexn2pro_v5"]

        self.assertEqual(record["provider"], "openrouter")
        self.assertEqual(record["model"], "nex-agi/nex-n2-pro:free")
        self.assertEqual(record["status"], QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE)
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 5)
        self.assertEqual(record["run_id"], 33233007435)
        self.assertEqual(
            record["head_sha"],
            "e52138287f9a98d83e8ddf2ca0e34a427f1c1c40",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")

        expected_failures = ["provider_transport:invalid_output", "http_status:404"]
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": expected_failures,
                "run413-bok-kmib-outlook-child": expected_failures,
                "run413-kpop-alphadriveone-actor-preserved": expected_failures,
                "run413-kbo-osen-same-game-source": expected_failures,
            },
        )
        self.assertEqual(record["artifact_id"], 9709072951)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:fa488a030134094d2e30ea0850cfeb269a9a49ff167625544b301019274dfa2c",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:6878028b25ec743f29701c94248906eb1aa7a006231e8c119c02dd5a42f79285",
        )

        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["provider_inventory_status"], CANDIDATE_QUALIFICATION_BLOCKED)
        self.assertEqual(payload["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertFalse(payload["full_production_correctness_claimed"])

    def test_consumed_one_shot_lane_is_absent(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("semantic-v5-provider-candidate-openrouter-nex-n2-pro", workflow)
        self.assertNotIn("[semantic-v5-candidate:openrouter-nex-n2-pro]", workflow)
        self.assertNotIn("qualify_openrouter_nexn2pro_v5", workflow)
        self.assertNotIn("event-understanding-v5-openrouter-nex-n2-pro-candidate", workflow)


if __name__ == "__main__":
    unittest.main()
