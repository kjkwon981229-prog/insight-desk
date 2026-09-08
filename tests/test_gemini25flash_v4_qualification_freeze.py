from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
CI_PATH = ROOT / ".github/workflows/ci.yml"


class Gemini25FlashV4QualificationFreezeTests(unittest.TestCase):
    def test_exact_provider_unavailable_evidence_is_frozen(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["gemini_25_flash_v4"]

        self.assertEqual(record["provider"], "gemini")
        self.assertEqual(record["model"], "gemini-2.5-flash")
        self.assertEqual(record["status"], "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE")
        self.assertEqual(record["existing_responsibility"], "event_understanding_candidate")
        self.assertEqual(record["qualification_protocol"], 4)
        self.assertEqual(record["run_id"], 33160640114)
        self.assertEqual(record["head_sha"], "ddd824b9a5c5d491f1db331a3b05d84f83b2d87a")
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")
        self.assertEqual(
            record["case_failures"],
            {
                case_id: ["provider_transport:invalid_output", "http_status:404"]
                for case_id in (
                    "run413-bok-kbs-rate-decision",
                    "run413-bok-kmib-outlook-child",
                    "run413-kpop-alphadriveone-actor-preserved",
                    "run413-kbo-osen-same-game-source",
                )
            },
        )
        self.assertEqual(record["artifact_id"], 9681493475)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:41d62d4fccae04ff2d12ee4ccb633d2d54ff9b78134821b1668a112b427e02bf",
        )
        self.assertEqual(
            record["report_digest"],
            "sha256:163a6b75147d39da5cb046c0dac99d0c44ad8c78e04e214b3bd8e5a686c252a1",
        )
        self.assertLess(record["qualification_protocol"], payload["active_qualification_protocol"])

    def test_invalid_harness_run_is_not_provider_evidence(self) -> None:
        record = load_provider_status(STATUS_PATH)["providers"]["gemini_25_flash_v4"]
        self.assertNotEqual(record["run_id"], 33160317727)
        self.assertNotEqual(record["head_sha"], "f5a108402e5a416080467386de8e37697f75a2a0")
        self.assertNotEqual(record["artifact_id"], 9681363458)
        self.assertNotEqual(
            record["artifact_digest"],
            "sha256:d9b8453d084cff7f3a83fb26523588c2749663ac2554d6228a711baccd49cadf",
        )
        self.assertNotEqual(
            record["report_digest"],
            "sha256:766c864ecd0b84943d6c3e6d6441968a205c611a0f07aead13a83655d5e4815c",
        )

    def test_consumed_one_shot_lane_is_removed_after_freeze(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("  semantic-v4-provider-candidate-gemini25flash-generatecontent:\n", workflow)
        self.assertNotIn("[semantic-v4-candidate:gemini-2.5-flash]", workflow)
        self.assertNotIn("qualify_gemini25_flash_v4", workflow)
        self.assertNotIn("event-understanding-gemini25-flash-v4", workflow)


if __name__ == "__main__":
    unittest.main()
