from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenRouterGpt54MiniQualificationEvidenceTests(unittest.TestCase):
    def test_first_v3_result_is_frozen_as_provider_unavailable(self) -> None:
        status = json.loads(
            (ROOT / "config/event_understanding_provider_status_v2.json").read_text(
                encoding="utf-8"
            )
        )
        provider = status["providers"]["openrouter_gpt54mini"]
        self.assertEqual(provider["model"], "openai/gpt-5.4-mini")
        self.assertEqual(provider["status"], "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE")
        self.assertEqual(provider["qualification_protocol"], 3)
        self.assertEqual(provider["run_id"], 33114677609)
        self.assertEqual(
            provider["head_sha"],
            "8a2cab78ef9451f81f7e3b1103664c532e1aaef1",
        )
        self.assertEqual(provider["evaluated_cases"], 4)
        self.assertEqual(provider["passed_cases"], 0)
        self.assertEqual(provider["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")
        self.assertEqual(provider["artifact_id"], 9664008294)
        self.assertEqual(
            provider["artifact_digest"],
            "sha256:628cfc8eafea59c4cfd779b250b4839d300a87913be4f06a7beb8f6bab6c91f6",
        )
        expected = ["provider_transport:invalid_output", "http_status:404"]
        self.assertEqual(
            provider["case_failures"],
            {
                "run413-bok-kbs-rate-decision": expected,
                "run413-bok-kmib-outlook-child": expected,
                "run413-kpop-alphadriveone-actor-preserved": expected,
                "run413-kbo-osen-same-game-source": expected,
            },
        )


if __name__ == "__main__":
    unittest.main()
