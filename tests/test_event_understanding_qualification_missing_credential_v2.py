from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import qualify_event_understanding_provider as qualification


class EventUnderstandingQualificationMissingCredentialTests(unittest.TestCase):
    def test_mistral_missing_key_returns_not_configured_without_evaluating_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with patch.dict("os.environ", {"MISTRAL_API_KEY": ""}, clear=False):
                code = qualification.qualify(
                    provider="mistral",
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )
            self.assertEqual(code, 2)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "NOT_CONFIGURED")
            self.assertEqual(payload["provider"], "mistral")
            self.assertEqual(payload["evaluated_cases"], 0)
            self.assertEqual(payload["passed_cases"], 0)
            self.assertFalse(payload["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
