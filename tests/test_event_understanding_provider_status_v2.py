from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    QUALIFICATION_BLOCKED_CREDENTIAL,
    load_provider_status,
    selected_provider,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingProviderStatusV2Tests(unittest.TestCase):
    def test_current_frozen_status_has_no_eligible_provider_and_no_wiring(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        self.assertIsNone(selected_provider(payload))
        self.assertFalse(payload["production_wired"])
        self.assertEqual(payload["active_qualification_protocol"], 2)
        self.assertEqual(
            payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER
        )
        self.assertEqual(payload["providers"]["groq_20b"]["status"], "NOT_QUALIFIED")
        self.assertEqual(
            payload["providers"]["gemini_flash_lite"]["status"], "NOT_QUALIFIED"
        )
        mistral = payload["providers"]["mistral_large_3"]
        self.assertEqual(mistral["status"], "NOT_QUALIFIED")
        self.assertEqual(mistral["evaluated_cases"], 4)
        self.assertEqual(mistral["passed_cases"], 0)
        self.assertEqual(mistral["failure_classification"], "ContractError")
        openrouter = payload["providers"]["openrouter_nemotron_free"]
        self.assertEqual(openrouter["status"], "NOT_QUALIFIED")
        self.assertEqual(openrouter["qualification_protocol"], 2)
        self.assertEqual(openrouter["run_id"], 33069019702)
        self.assertEqual(openrouter["evaluated_cases"], 4)
        self.assertEqual(openrouter["passed_cases"], 0)
        self.assertEqual(
            openrouter["failure_classification"],
            "MIXED_CONTRACT_AND_INVALID_OUTPUT",
        )
        for case_id in (
            "run413-bok-kbs-rate-decision",
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
        ):
            self.assertEqual(
                openrouter["case_failures"][case_id],
                ["provider_or_contract_error:ContractError"],
            )
        self.assertEqual(
            openrouter["case_failures"]["run413-kbo-osen-same-game-source"],
            ["provider_transport:invalid_output"],
        )
        self.assertEqual(openrouter["artifact_id"], 9644987975)
        self.assertEqual(openrouter["previous_v1_evidence"]["passed_cases"], 1)
        self.assertEqual(openrouter["previous_v1_evidence"]["run_id"], 33057003750)
        self.assertEqual(payload["providers"]["groq_120b"]["status"], "EXCLUDED")
        self.assertEqual(
            payload["providers"]["cloudflare_llama_70b"]["existing_responsibility"],
            "verification_primary",
        )
        self.assertEqual(
            payload["providers"]["local_nli"]["existing_responsibility"],
            "verification_secondary",
        )

    def test_unqualified_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "groq_20b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_openrouter_unqualified_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "openrouter_nemotron_free"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_excluded_120b_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "groq_120b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_credential_blocked_candidate_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["credential_blocked"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": QUALIFICATION_BLOCKED_CREDENTIAL,
            "evaluated_cases": 0,
            "preflight_result": "NOT_CONFIGURED",
        }
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "credential_blocked"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_blocked_inventory_prevents_selection_even_for_synthetic_pass(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["future_candidate"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
        }
        mutated["selected_event_understanding_provider"] = "future_candidate"
        with self.assertRaisesRegex(ContractError, "not eligible"):
            validate_provider_status(mutated)

    def test_credential_block_requires_zero_cases_and_not_configured_preflight(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["credential_blocked"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": QUALIFICATION_BLOCKED_CREDENTIAL,
            "evaluated_cases": 1,
            "preflight_result": "NOT_CONFIGURED",
        }
        with self.assertRaisesRegex(ContractError, "zero cases"):
            validate_provider_status(mutated)
        mutated = deepcopy(payload)
        mutated["providers"]["credential_blocked"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": QUALIFICATION_BLOCKED_CREDENTIAL,
            "evaluated_cases": 0,
            "preflight_result": "NOT_QUALIFIED",
        }
        with self.assertRaisesRegex(ContractError, "NOT_CONFIGURED"):
            validate_provider_status(mutated)

    def test_production_wiring_requires_selected_qualified_provider(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["production_wired"] = True
        with self.assertRaisesRegex(ContractError, "without a selected provider"):
            validate_provider_status(mutated)

    def test_explicit_inventory_and_provider_pass_are_both_required_for_selection(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["future_candidate"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
        }
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "future_candidate"
        validate_provider_status(mutated)
        self.assertEqual(selected_provider(mutated), "future_candidate")


if __name__ == "__main__":
    unittest.main()
