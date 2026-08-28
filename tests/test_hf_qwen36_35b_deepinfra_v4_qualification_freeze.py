from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class HFQwen36_35BDeepInfraV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_mixed_nonpass_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["hf_qwen36_35b_deepinfra_v4"]

        self.assertEqual(record["provider"], "huggingface")
        self.assertEqual(record["model"], "Qwen/Qwen3.6-35B-A3B:deepinfra")
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33166122207)
        self.assertEqual(
            record["head_sha"],
            "3d716e45f8031b48fbc47c6a6110b5d580809252",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(
            record["failure_classification"],
            "MIXED_INVALID_OUTPUT_AND_TRANSIENT_FAILURE",
        )
        self.assertEqual(
            record["case_failures"],
            {
                "run413-bok-kbs-rate-decision": ["provider_transport:invalid_output"],
                "run413-bok-kmib-outlook-child": ["provider_transport:transient_provider"],
                "run413-kpop-alphadriveone-actor-preserved": ["provider_transport:invalid_output"],
                "run413-kbo-osen-same-game-source": ["provider_transport:transient_provider"],
            },
        )
        self.assertEqual(record["artifact_id"], 9683792273)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:fa52047919a441da4ad819ad39b257df5e58ef7721c5c0055c545f8e3addd81f",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:e2807cc45d6a2e45e653ced1831275b7363981b2d3b9ba90eb99ab208d025017",
        )

        self.assertEqual(payload["active_qualification_protocol"], 4)
        self.assertEqual(payload["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])

    def test_mixed_definitive_and_transient_result_is_not_reclassified_as_blocked(self) -> None:
        record = load_provider_status(STATUS_PATH)["providers"]["hf_qwen36_35b_deepinfra_v4"]
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        definitive = [
            case_id
            for case_id, failures in record["case_failures"].items()
            if "provider_transport:invalid_output" in failures
        ]
        transient = [
            case_id
            for case_id, failures in record["case_failures"].items()
            if "provider_transport:transient_provider" in failures
        ]
        self.assertEqual(
            definitive,
            [
                "run413-bok-kbs-rate-decision",
                "run413-kpop-alphadriveone-actor-preserved",
            ],
        )
        self.assertEqual(
            transient,
            [
                "run413-bok-kmib-outlook-child",
                "run413-kbo-osen-same-game-source",
            ],
        )

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "  semantic-v4-provider-candidate-hf-qwen36-35b-deepinfra:\n",
            workflow,
        )
        self.assertNotIn("[semantic-v4-candidate:hf-qwen36-35b-deepinfra]", workflow)
        self.assertNotIn("qualify_hf_qwen36_35b_deepinfra_v4", workflow)
        self.assertNotIn("event-understanding-hf-qwen36-35b-deepinfra-v4", workflow)


if __name__ == "__main__":
    unittest.main()
