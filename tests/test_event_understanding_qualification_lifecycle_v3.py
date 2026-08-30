from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from insight_desk.core import FailureKind
from insight_desk.providers.transport import ProviderTransportError
from scripts import qualify_event_understanding_provider as qualification


class _TransientStructuredClient:
    def structured_json(self, **kwargs):
        raise ProviderTransportError(failure_kind=FailureKind.TRANSIENT_PROVIDER)


class EventUnderstandingQualificationLifecycleV3Tests(unittest.TestCase):
    def test_all_transient_provider_failures_are_inconclusive_not_not_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with (
                patch.object(qualification, "_provider_configured", return_value=True),
                patch.object(
                    qualification,
                    "_provider_client",
                    return_value=(_TransientStructuredClient(), "transient-fixture-model"),
                ),
            ):
                code = qualification.qualify(
                    provider="mistral",
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(code, 3)
            self.assertEqual(payload["status"], "QUALIFICATION_BLOCKED_TRANSIENT")
            self.assertEqual(payload["evaluated_cases"], 4)
            self.assertEqual(payload["passed_cases"], 0)
            self.assertEqual(
                {failure for case in payload["cases"] for failure in case["failures"]},
                {"provider_transport:transient_provider"},
            )

    def test_invalid_output_remains_a_definitive_not_qualified_result(self) -> None:
        case_reports = [
            {
                "case_id": "case-1",
                "passed": False,
                "failures": ["provider_transport:invalid_output"],
            }
        ]
        self.assertEqual(
            qualification._qualification_outcome(case_reports),
            "NOT_QUALIFIED",
        )

    def test_partial_pass_plus_transient_is_still_inconclusive(self) -> None:
        case_reports = [
            {"case_id": "case-1", "passed": True, "failures": []},
            {
                "case_id": "case-2",
                "passed": False,
                "failures": ["provider_transport:transient_provider", "http_status:503"],
            },
        ]
        self.assertEqual(
            qualification._qualification_outcome(case_reports),
            "QUALIFICATION_BLOCKED_TRANSIENT",
        )


if __name__ == "__main__":
    unittest.main()
