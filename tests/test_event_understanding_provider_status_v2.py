from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    AWAITING_PROVIDER_QUALIFICATION,
    CANDIDATE_QUALIFICATION_BLOCKED,
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    QUALIFICATION_BLOCKED_CREDENTIAL,
    QUALIFICATION_BLOCKED_TRANSIENT,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    selected_provider,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingProviderStatusV2Tests(unittest.TestCase):
    def test_current_status_preserves_historical_evidence_and_unselected_v5_state(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        self.assertIsNone(selected_provider(payload))
        self.assertFalse(payload["production_wired"])
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["contract"], "event_understanding_v2")
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(payload["active_qualification_protocol"], 5)
        self.assertEqual(payload["qualification_contract_status"], AWAITING_PROVIDER_QUALIFICATION)
        self.assertEqual(payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)

        groq = payload["providers"]["groq_20b"]
        self.assertEqual(groq["status"], "NOT_QUALIFIED")
        self.assertEqual(groq["qualification_protocol"], 1)
        gemini = payload["providers"]["gemini_flash_lite"]
        self.assertEqual(gemini["status"], "NOT_QUALIFIED")
        self.assertEqual(gemini["qualification_protocol"], 1)

        mistral = payload["providers"]["mistral_large_3"]
        self.assertEqual(mistral["status"], QUALIFICATION_BLOCKED_TRANSIENT)
        self.assertEqual(mistral["qualification_protocol"], 3)
        self.assertEqual(mistral["run_id"], 33094503683)
        self.assertEqual(mistral["head_sha"], "a417ac291031358e547b00d59bccce2412fb9044")
        self.assertEqual(mistral["raw_run_status"], "NOT_QUALIFIED")
        self.assertEqual(mistral["evaluated_cases"], 4)
        self.assertEqual(mistral["passed_cases"], 0)
        self.assertEqual(mistral["failure_classification"], "PROVIDER_TRANSIENT_FAILURE")
        for case_id in (
            "run413-bok-kbs-rate-decision",
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
            "run413-kbo-osen-same-game-source",
        ):
            self.assertEqual(mistral["case_failures"][case_id], ["provider_transport:transient_provider"])
        self.assertEqual(mistral["artifact_id"], 9656236318)
        self.assertEqual(mistral["previous_v1_evidence"]["qualification_protocol"], 1)

        openrouter = payload["providers"]["openrouter_nemotron_free"]
        self.assertEqual(openrouter["status"], "NOT_QUALIFIED")
        self.assertEqual(openrouter["qualification_protocol"], 3)
        self.assertEqual(openrouter["run_id"], 33093075809)
        self.assertEqual(openrouter["head_sha"], "84ec074fda93d7fa1e4537e6bbfde26d5a58eb31")
        self.assertEqual(openrouter["evaluated_cases"], 4)
        self.assertEqual(openrouter["passed_cases"], 0)
        self.assertEqual(openrouter["case_failures"]["run413-kbo-osen-same-game-source"], ["adapter_contract:evidence_contract"])
        self.assertEqual(openrouter["artifact_id"], 9655338800)
        self.assertEqual(openrouter["previous_v2_evidence"]["qualification_protocol"], 2)
        self.assertEqual(openrouter["previous_v1_evidence"]["qualification_protocol"], 1)

        qwen = payload["providers"]["groq_qwen38_27b"]
        self.assertEqual(qwen["model"], "qwen/qwen3.8-27b")
        self.assertEqual(qwen["status"], "NOT_QUALIFIED")
        self.assertEqual(qwen["qualification_protocol"], 3)
        self.assertEqual(qwen["run_id"], 33109809796)
        self.assertEqual(qwen["failure_classification"], "MIXED_ADAPTER_AND_SEMANTIC_FAILURE")
        self.assertEqual(qwen["case_failures"]["run413-bok-kmib-outlook-child"], ["event_drafts_min", "expected_event_match", "parent_hint_min"])

        hf = payload["providers"]["hf_qwen235b2507_nscale"]
        self.assertEqual(hf["model"], "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale")
        self.assertEqual(hf["status"], "NOT_QUALIFIED")
        self.assertEqual(hf["qualification_protocol"], 3)
        self.assertEqual(hf["run_id"], 33136814090)
        self.assertEqual(hf["failure_classification"], "EVIDENCE_CONTRACT")
        self.assertEqual(hf["artifact_id"], 9672398678)

        gemini35_v4 = payload["providers"]["gemini_35_flash_v4"]
        self.assertEqual(gemini35_v4["status"], "NOT_QUALIFIED")
        self.assertEqual(gemini35_v4["qualification_protocol"], 4)
        self.assertEqual(gemini35_v4["evaluated_cases"], 4)
        self.assertEqual(gemini35_v4["passed_cases"], 3)

        gemini36_v4 = payload["providers"]["gemini_36_flash_v4"]
        self.assertEqual(gemini36_v4["status"], "NOT_QUALIFIED")
        self.assertEqual(gemini36_v4["qualification_protocol"], 4)
        self.assertEqual(gemini36_v4["evaluated_cases"], 4)
        self.assertEqual(gemini36_v4["passed_cases"], 3)
        self.assertEqual(gemini36_v4["run_id"], 33144497986)
        self.assertEqual(gemini36_v4["failure_classification"], "CHILD_EVENT_SEMANTIC_FAILURE")
        self.assertEqual(
            gemini36_v4["case_failures"]["run413-bok-kmib-outlook-child"],
            ["event_drafts_min", "expected_event_match", "parent_hint_min"],
        )

        gemini25_v4 = payload["providers"]["gemini_25_pro_v4"]
        self.assertEqual(gemini25_v4["status"], "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE")
        self.assertEqual(gemini25_v4["qualification_protocol"], 4)
        self.assertEqual(gemini25_v4["evaluated_cases"], 4)
        self.assertEqual(gemini25_v4["passed_cases"], 0)
        self.assertEqual(gemini25_v4["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")

        gemini35lite_v4 = payload["providers"]["gemini_35_flash_lite_v4"]
        self.assertEqual(gemini35lite_v4["status"], "NOT_QUALIFIED")
        self.assertEqual(gemini35lite_v4["qualification_protocol"], 4)
        self.assertEqual(gemini35lite_v4["evaluated_cases"], 4)
        self.assertEqual(gemini35lite_v4["passed_cases"], 1)
        self.assertEqual(gemini35lite_v4["failure_classification"], "EVENT_DRAFT_CONTRACT")

        gemini25flash_v4 = payload["providers"]["gemini_25_flash_v4"]
        self.assertEqual(gemini25flash_v4["model"], "gemini-2.5-flash")
        self.assertEqual(
            gemini25flash_v4["status"],
            "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE",
        )
        self.assertEqual(gemini25flash_v4["qualification_protocol"], 4)
        self.assertEqual(gemini25flash_v4["run_id"], 33160640114)
        self.assertEqual(gemini25flash_v4["evaluated_cases"], 4)
        self.assertEqual(gemini25flash_v4["passed_cases"], 0)
        self.assertEqual(
            gemini25flash_v4["failure_classification"],
            "PROVIDER_MODEL_UNAVAILABLE",
        )

        hf_qwen36_v4 = payload["providers"]["hf_qwen36_35b_deepinfra_v4"]
        self.assertEqual(hf_qwen36_v4["model"], "Qwen/Qwen3.6-35B-A3B:deepinfra")
        self.assertEqual(hf_qwen36_v4["status"], "NOT_QUALIFIED")
        self.assertEqual(hf_qwen36_v4["qualification_protocol"], 4)
        self.assertEqual(hf_qwen36_v4["run_id"], 33166122207)
        self.assertEqual(hf_qwen36_v4["evaluated_cases"], 4)
        self.assertEqual(hf_qwen36_v4["passed_cases"], 0)
        self.assertEqual(
            hf_qwen36_v4["failure_classification"],
            "MIXED_INVALID_OUTPUT_AND_TRANSIENT_FAILURE",
        )

        cerebras_gemma_v4 = payload["providers"]["cerebras_gemma4_31b_v4"]
        self.assertEqual(cerebras_gemma_v4["model"], "gemma-4-31b")
        self.assertEqual(cerebras_gemma_v4["status"], "NOT_QUALIFIED")
        self.assertEqual(cerebras_gemma_v4["qualification_protocol"], 4)
        self.assertEqual(cerebras_gemma_v4["run_id"], 33168432708)
        self.assertEqual(cerebras_gemma_v4["evaluated_cases"], 4)
        self.assertEqual(cerebras_gemma_v4["passed_cases"], 0)
        self.assertEqual(
            cerebras_gemma_v4["failure_classification"],
            "ZERO_COST_ACCESS_UNAVAILABLE",
        )

        mistral_medium35_v5 = payload["providers"]["mistral_medium35_v5"]
        self.assertEqual(mistral_medium35_v5["model"], "mistral-medium-3-5")
        self.assertEqual(mistral_medium35_v5["status"], "NOT_QUALIFIED")
        self.assertEqual(mistral_medium35_v5["qualification_protocol"], 5)
        self.assertEqual(mistral_medium35_v5["run_id"], 33180474834)
        self.assertEqual(mistral_medium35_v5["evaluated_cases"], 4)
        self.assertEqual(mistral_medium35_v5["passed_cases"], 3)
        self.assertEqual(
            mistral_medium35_v5["failure_classification"],
            "EVENT_MATCH_SEMANTIC_FAILURE",
        )
        self.assertEqual(
            mistral_medium35_v5["case_failures"],
            {"run413-kbo-osen-same-game-source": ["expected_event_match"]},
        )

        active_protocol = payload["active_qualification_protocol"]
        active_records = []
        for provider_id, record in payload["providers"].items():
            protocol = record.get("qualification_protocol")
            if protocol is not None:
                with self.subTest(provider_id=provider_id):
                    self.assertLessEqual(protocol, active_protocol)
                if protocol == active_protocol:
                    active_records.append(record)
        self.assertTrue(active_records)
        self.assertTrue(all(record.get("status") != MINIMUM_COMPATIBILITY_PASS for record in active_records))

        self.assertEqual(payload["providers"]["groq_120b"]["status"], "EXCLUDED")
        self.assertEqual(payload["providers"]["cloudflare_llama_70b"]["existing_responsibility"], "verification_primary")
        self.assertEqual(payload["providers"]["local_nli"]["existing_responsibility"], "verification_secondary")

    @staticmethod
    def _mark_selection_state(mutated: dict[str, object]) -> None:
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE

    @staticmethod
    def _active_v5_baseline(payload: dict[str, object]) -> dict[str, object]:
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = NO_ELIGIBLE_EXISTING_PROVIDER
        validate_provider_status(mutated)
        return mutated

    def test_unqualified_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "groq_20b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_stale_v4_blocks_do_not_block_current_inventory(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = self._active_v5_baseline(payload)
        mutated["provider_inventory_status"] = CANDIDATE_QUALIFICATION_BLOCKED
        with self.assertRaisesRegex(ContractError, "NO_ELIGIBLE_EXISTING_PROVIDER"):
            validate_provider_status(mutated)

    def test_historical_transient_record_still_rejects_semantic_failure_codes(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["mistral_large_3"]["case_failures"]["run413-bok-kbs-rate-decision"] = ["expected_event_match"]
        with self.assertRaisesRegex(ContractError, "definitive failure"):
            validate_provider_status(mutated)

    def test_excluded_provider_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "groq_120b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_active_v5_credential_block_is_not_selectable_and_requires_blocked_inventory(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = self._active_v5_baseline(payload)
        mutated["providers"]["credential_blocked"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": QUALIFICATION_BLOCKED_CREDENTIAL,
            "qualification_protocol": 5,
            "evaluated_cases": 0,
            "preflight_result": "NOT_CONFIGURED",
        }
        with self.assertRaisesRegex(ContractError, "CANDIDATE_QUALIFICATION_BLOCKED"):
            validate_provider_status(mutated)

        mutated["provider_inventory_status"] = CANDIDATE_QUALIFICATION_BLOCKED
        validate_provider_status(mutated)

        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "credential_blocked"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_credential_block_requires_zero_cases_and_not_configured_preflight(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["credential_blocked"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": QUALIFICATION_BLOCKED_CREDENTIAL,
            "qualification_protocol": 5,
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
            "qualification_protocol": 5,
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
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "historical_pass"
        with self.assertRaisesRegex(ContractError, "stale protocol"):
            validate_provider_status(mutated)

    def test_current_v5_pass_can_be_selected_despite_stale_v4_blocks(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["future_candidate"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
            "qualification_protocol": 5,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        self._mark_selection_state(mutated)
        mutated["selected_event_understanding_provider"] = "future_candidate"
        validate_provider_status(mutated)
        self.assertEqual(selected_provider(mutated), "future_candidate")


if __name__ == "__main__":
    unittest.main()
