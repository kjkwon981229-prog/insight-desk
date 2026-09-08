from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    QUALIFICATION_BLOCKED_TRANSIENT,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class Gemini37ProviderStatusFreezeTests(unittest.TestCase):
    def test_frozen_transient_evidence_is_exact_and_not_selectable(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        gemini = payload["providers"]["gemini_37_flash"]
        self.assertEqual(gemini["provider"], "gemini")
        self.assertEqual(gemini["model"], "gemini-3.7-flash")
        self.assertEqual(gemini["status"], QUALIFICATION_BLOCKED_TRANSIENT)
        self.assertEqual(gemini["qualification_protocol"], 3)
        self.assertEqual(gemini["run_id"], 33111216988)
        self.assertEqual(
            gemini["head_sha"],
            "38cbd5c430eef9f5e96f461b2039db4e1f0ba8a7",
        )
        self.assertEqual(gemini["evaluated_cases"], 4)
        self.assertEqual(gemini["passed_cases"], 0)
        self.assertEqual(gemini["failure_classification"], "PROVIDER_TRANSIENT_FAILURE")
        self.assertEqual(
            gemini["case_failures"]["run413-bok-kbs-rate-decision"],
            ["provider_transport:transient_provider", "http_status:500"],
        )
        for case_id in (
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
            "run413-kbo-osen-same-game-source",
        ):
            self.assertEqual(
                gemini["case_failures"][case_id],
                ["provider_transport:rate_limited", "http_status:429"],
            )
        self.assertEqual(gemini["artifact_id"], 9662688106)
        self.assertEqual(
            gemini["artifact_digest"],
            "sha256:7c464425cf1ddaede9458905664f4b1038e81b1d7a10c5e1f0c72cc01e8d1371",
        )

        mutated = deepcopy(payload)
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "gemini_37_flash"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)


if __name__ == "__main__":
    unittest.main()
