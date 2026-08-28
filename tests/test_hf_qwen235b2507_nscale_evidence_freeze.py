from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class HuggingFaceQwen235B2507NscaleEvidenceFreezeTests(unittest.TestCase):
    def test_exact_v3_not_qualified_evidence_is_frozen(self) -> None:
        status = load_provider_status(STATUS_PATH)
        record = status["providers"]["hf_qwen235b2507_nscale"]

        self.assertEqual(record["provider"], "huggingface")
        self.assertEqual(
            record["model"],
            "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale",
        )
        self.assertEqual(record["status"], "NOT_QUALIFIED")
        self.assertEqual(record["qualification_protocol"], 3)
        self.assertEqual(record["run_id"], 33136814090)
        self.assertEqual(
            record["head_sha"],
            "ac8057b88f46439ecaf45f59a73aa3ebc6112229",
        )
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "EVIDENCE_CONTRACT")
        self.assertEqual(record["artifact_id"], 9672398678)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:1f1f1388667e14b5836bb0b0aad4f4d719210cdcd62a1f2942acfe922124a339",
        )
        self.assertEqual(
            set(record["case_failures"]),
            {
                "run413-bok-kbs-rate-decision",
                "run413-bok-kmib-outlook-child",
                "run413-kpop-alphadriveone-actor-preserved",
                "run413-kbo-osen-same-game-source",
            },
        )
        for failures in record["case_failures"].values():
            self.assertEqual(failures, ["adapter_contract:evidence_contract"])

        self.assertEqual(status["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])


if __name__ == "__main__":
    unittest.main()
