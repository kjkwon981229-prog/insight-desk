from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class OpenRouterGlm52ProviderStatusFreezeTests(unittest.TestCase):
    def test_frozen_mixed_failure_evidence_is_exact_and_not_selectable(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        provider = payload["providers"]["openrouter_glm52_free"]
        self.assertEqual(provider["provider"], "openrouter")
        self.assertEqual(provider["model"], "z-ai/glm-5.2:free")
        self.assertEqual(provider["status"], "NOT_QUALIFIED")
        self.assertEqual(provider["qualification_protocol"], 3)
        self.assertEqual(provider["run_id"], 33113044704)
        self.assertEqual(
            provider["head_sha"],
            "33fb4969807387fc1ea4662300397da7a6bf34d9",
        )
        self.assertEqual(provider["evaluated_cases"], 4)
        self.assertEqual(provider["passed_cases"], 0)
        self.assertEqual(
            provider["failure_classification"],
            "MIXED_ADAPTER_AND_RATE_LIMIT_FAILURE",
        )
        self.assertEqual(
            provider["case_failures"]["run413-bok-kbs-rate-decision"],
            ["provider_transport:rate_limited", "http_status:429"],
        )
        self.assertEqual(
            provider["case_failures"]["run413-bok-kmib-outlook-child"],
            ["adapter_contract:event_draft_contract"],
        )
        self.assertEqual(
            provider["case_failures"]["run413-kpop-alphadriveone-actor-preserved"],
            ["adapter_contract:evidence_contract"],
        )
        self.assertEqual(
            provider["case_failures"]["run413-kbo-osen-same-game-source"],
            ["provider_transport:rate_limited", "http_status:429"],
        )
        self.assertEqual(provider["artifact_id"], 9663362476)
        self.assertEqual(
            provider["artifact_digest"],
            "sha256:4e47046aba32c8d045ac63a259eaf0f18b786c9845c6b0eb4a6686cdf12b289e",
        )

        mutated = deepcopy(payload)
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "openrouter_glm52_free"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)


if __name__ == "__main__":
    unittest.main()
