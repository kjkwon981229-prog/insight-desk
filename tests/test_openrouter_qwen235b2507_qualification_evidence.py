from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OpenRouterQwen235B2507QualificationEvidenceTests(unittest.TestCase):
    def test_first_v3_result_is_frozen_as_provider_unavailable(self) -> None:
        status = json.loads(
            (ROOT / "config/event_understanding_provider_status_v2.json").read_text(
                encoding="utf-8"
            )
        )
        provider = status["providers"]["openrouter_qwen235b2507_free"]
        self.assertEqual(provider["model"], "qwen/qwen3-235b-a22b-2507:free")
        self.assertEqual(provider["status"], "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE")
        self.assertEqual(provider["qualification_protocol"], 3)
        self.assertEqual(provider["run_id"], 33124330887)
        self.assertEqual(
            provider["head_sha"],
            "82495636bfb2b5392ade94f4066ce444ada012ae",
        )
        self.assertEqual(provider["evaluated_cases"], 4)
        self.assertEqual(provider["passed_cases"], 0)
        self.assertEqual(provider["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")
        self.assertEqual(provider["artifact_id"], 9667744179)
        self.assertEqual(
            provider["artifact_digest"],
            "sha256:050415d8931c36a4b1c05c5a5608b05d2b0c6ee2e45f27c31ee56dc8d83504ed",
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
