from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class CerebrasQualificationFreezeV3Tests(unittest.TestCase):
    def test_cerebras_404_result_is_frozen_as_provider_unavailable(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        record = payload["providers"]["cerebras_glm_47"]
        self.assertEqual(record["provider"], "cerebras")
        self.assertEqual(record["model"], "zai-glm-4.7")
        self.assertEqual(record["status"], QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE)
        self.assertEqual(record["qualification_protocol"], 3)
        self.assertEqual(record["run_id"], 33107187962)
        self.assertEqual(record["head_sha"], "3fd4716da29907ed7ca1867d26315b6959684f39")
        self.assertEqual(record["raw_run_status"], "NOT_QUALIFIED")
        self.assertEqual(record["evaluated_cases"], 4)
        self.assertEqual(record["passed_cases"], 0)
        self.assertEqual(record["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")
        self.assertEqual(record["artifact_id"], 9660968622)
        self.assertEqual(
            record["artifact_digest"],
            "sha256:4393d0cf8764142da6130a98fa04ee36c20e1f7fb4b7ead7bfacbf9662dbf862",
        )
        self.assertEqual(len(record["case_failures"]), 4)
        for failures in record["case_failures"].values():
            self.assertEqual(failures, ["provider_transport:invalid_output", "http_status:404"])
        self.assertLess(record["qualification_protocol"], payload["active_qualification_protocol"])
        self.assertIsNone(payload["selected_event_understanding_provider"])
        self.assertFalse(payload["production_wired"])
        self.assertEqual(payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)

    def test_provider_unavailable_candidate_cannot_be_selected(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["selected_event_understanding_provider"] = "cerebras_glm_47"
        with self.assertRaisesRegex(ContractError, "not qualified"):
            validate_provider_status(mutated)

    def test_provider_unavailable_freeze_rejects_non_404_failure(self) -> None:
        payload = load_provider_status(STATUS_PATH)
        mutated = deepcopy(payload)
        mutated["providers"]["cerebras_glm_47"]["case_failures"][
            "run413-bok-kbs-rate-decision"
        ] = ["expected_event_match"]
        with self.assertRaisesRegex(ContractError, "non-404"):
            validate_provider_status(mutated)


if __name__ == "__main__":
    unittest.main()
