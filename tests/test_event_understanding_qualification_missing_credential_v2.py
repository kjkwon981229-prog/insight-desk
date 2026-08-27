from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import qualify_event_understanding_provider as qualification


class EventUnderstandingQualificationMissingCredentialTests(unittest.TestCase):
    def _assert_not_configured(self, *, provider: str, env_name: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with patch.dict("os.environ", {env_name: ""}, clear=False):
                code = qualification.qualify(
                    provider=provider,
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )
            self.assertEqual(code, 2)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "NOT_CONFIGURED")
            self.assertEqual(payload["provider"], provider)
            self.assertEqual(payload["evaluated_cases"], 0)
            self.assertEqual(payload["passed_cases"], 0)
            self.assertFalse(payload["full_production_correctness_claimed"])

    def test_mistral_missing_key_returns_not_configured_without_evaluating_cases(self) -> None:
        self._assert_not_configured(provider="mistral", env_name="MISTRAL_API_KEY")

    def test_openrouter_missing_key_returns_not_configured_without_evaluating_cases(self) -> None:
        self._assert_not_configured(
            provider="openrouter_nemotron",
            env_name="OPENROUTER_API_KEY",
        )


if __name__ == "__main__":
    unittest.main()
