from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    AWAITING_PROVIDER_QUALIFICATION,
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    QUALIFICATION_BLOCKED_CREDENTIAL,
    QUALIFIED_PROVIDER_SELECTED,
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
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["contract"], "event_understanding_v2")
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v2")
        self.assertEqual(payload["active_qualification_protocol"], 3)
        self.assertEqual(
            payload["qualification_contract_status"], AWAITING_PROVIDER_QUALIFICATION
        )
        self.assertEqual(
            payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER
        )
        groq = payload["providers"]["groq_20b"]
        self.assertEqual(groq["status"], "NOT_QUALIFIED")
        self.assertEqual(groq["qualification_protocol"], 1)
        gemini = payload["providers"]["gemini_flash_lite"]
        self.assertEqual(gemini["status"], "NOT_QUALIFIED")
        self.assertEqual(gemini["qualification_protocol"], 1)
        mistral = payload["providers"]["mistral_large_3"]
        self.assertEqual(mistral["status"], "NOT_QUALIFIED")
        self.assertEqual(mistral["qualification_protocol"], 1)
        self.assertEqual(mistral["evaluated_cases"], 4)
        self.assertEqual(mistral["passed_cases"], 0)
        self.assertEqual(mistral["failure_classification"], "ContractError")
        openrouter = payload["providers"]["openrouter_nemotron_free"]
        self.assertEqual(openrouter["status"], "NOT_QUALIFIED")
        self.assertEqual(openrouter["qualification_protocol"], 3)
        self.assertEqual(openrouter["run_id"], 33093075809)
        self.assertEqual(
            openrouter["head_sha"],
            "84ec074fda93d7fa1e4537e6bbfde26d5a58eb31",
        )
        self.assertEqual(openrouter["evaluated_cases"], 4)
        self.assertEqual(openrouter["passed_cases"], 0)
        for case_id in (
            "run413-bok-kbs-rate-decision",
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
        ):
            self.assertEqual(
                openrouter["case_failures"][case_id],
                ["provider_transport:invalid_output"],
            )
        self.assertEqual(
            openrouter["case_failures"]["run413-kbo-osen-same-game-source"],
            ["adapter_contract:evidence_contract"],
        )
        self.assertEqual(openrouter["artifact_id"], 9655338800)
        self.assertEqual(
            openrouter["artifact_digest"],
            "sha256:0f06113d6ce5e5affcadde365474bbd12d4016f88ed7fa54a97d8a4e625834dc",
        )
        self.assertEqual(openrouter["previous_v2_evidence"]["qualification_protocol"], 2)
        self.assertEqual(openrouter["previous_v2_evidence"]["run_id"], 33069019702)
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

    @staticmethod
    def _mark_selection_state(mutated: dict[str, object]) -> None:
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE

    def test_unqualified_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "groq_20b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_openrouter_unqualified_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "openrouter_nemotron_free"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_excluded_120b_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        self._mark_selection_state(mutated)
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
            "qualification_protocol": 3,
            "evaluated_cases": 0,
            "preflight_result": "NOT_CONFIGURED",
        }
        self._mark_selection_state(mutated)
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
            "qualification_protocol": 3,
            "evaluated_cases": 4,
        }
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
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
            "qualification_protocol": 3,
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
            "qualification_protocol": 3,
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

    def test_stale_protocol_pass_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["historical_pass"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
            "qualification_protocol": 2,
            "evaluated_cases": 4,
        }
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "historical_pass"
        with self.assertRaisesRegex(ContractError, "stale protocol"):
            validate_provider_status(mutated)

    def test_explicit_inventory_current_protocol_pass_is_required_for_selection(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["future_candidate"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
            "qualification_protocol": 3,
            "evaluated_cases": 4,
        }
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "future_candidate"
        validate_provider_status(mutated)
        self.assertEqual(selected_provider(mutated), "future_candidate")


if __name__ == "__main__":
    unittest.main()
