from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.providers.hf_qwen235b2507_nscale import HF_QWEN3_235B_2507_NSCALE
from scripts import qualify_event_understanding_provider as canonical
from scripts import qualify_hf_qwen235b2507_nscale as lane


class HuggingFaceQwen235B2507NscaleQualificationLaneTests(unittest.TestCase):
    def test_candidate_registration_is_scoped_and_exact(self) -> None:
        original_choices = canonical.PROVIDER_CHOICES
        original_model = canonical._provider_model
        original_configured = canonical._provider_configured
        original_client = canonical._provider_client

        with patch.dict(os.environ, {}, clear=True):
            with lane.registered_candidate_provider():
                self.assertEqual(canonical.PROVIDER_CHOICES[-1], lane.CANDIDATE_PROVIDER)
                self.assertEqual(
                    canonical._provider_model(lane.CANDIDATE_PROVIDER),
                    HF_QWEN3_235B_2507_NSCALE,
                )
                self.assertFalse(canonical._provider_configured(lane.CANDIDATE_PROVIDER))

        self.assertEqual(canonical.PROVIDER_CHOICES, original_choices)
        self.assertIs(canonical._provider_model, original_model)
        self.assertIs(canonical._provider_configured, original_configured)
        self.assertIs(canonical._provider_client, original_client)

    def test_missing_credential_reuses_canonical_v3_not_configured_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            with patch.dict(os.environ, {}, clear=True):
                code = lane.qualify(report_path=report_path)

            self.assertEqual(code, 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "NOT_CONFIGURED")
            self.assertEqual(report["provider"], lane.CANDIDATE_PROVIDER)
            self.assertEqual(report["model"], HF_QWEN3_235B_2507_NSCALE)
            self.assertEqual(report["qualification_protocol"], 3)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v2")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
