from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    load_provider_status,
    selected_provider,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingProviderStatusV2Tests(unittest.TestCase):
    def test_current_frozen_status_has_no_selected_or_wired_provider(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        self.assertIsNone(selected_provider(payload))
        self.assertFalse(payload["production_wired"])
        self.assertEqual(
            payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER
        )
        self.assertEqual(payload["providers"]["groq_20b"]["status"], "NOT_QUALIFIED")
        self.assertEqual(
            payload["providers"]["gemini_flash_lite"]["status"], "NOT_QUALIFIED"
        )
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

    def test_excluded_120b_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "groq_120b"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_provider_inventory_block_prevents_selection_even_for_synthetic_pass(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["future_candidate"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
        }
        mutated["selected_event_understanding_provider"] = "future_candidate"
        with self.assertRaisesRegex(ContractError, "no eligible"):
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
