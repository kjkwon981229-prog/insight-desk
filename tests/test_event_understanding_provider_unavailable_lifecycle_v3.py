from __future__ import annotations

import unittest

from scripts import qualify_event_understanding_provider as qualification


class EventUnderstandingProviderUnavailableLifecycleV3Tests(unittest.TestCase):
    def test_all_model_not_found_failures_are_provider_unavailable_not_not_qualified(self) -> None:
        case_reports = [
            {
                "case_id": f"case-{index}",
                "passed": False,
                "failures": ["provider_transport:invalid_output", "http_status:404"],
            }
            for index in range(1, 5)
        ]
        self.assertEqual(
            qualification._qualification_outcome(case_reports),
            "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE",
        )

    def test_plain_invalid_output_without_404_remains_definitive(self) -> None:
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

    def test_404_mixed_with_semantic_failure_remains_definitive(self) -> None:
        case_reports = [
            {
                "case_id": "case-1",
                "passed": False,
                "failures": ["provider_transport:invalid_output", "http_status:404"],
            },
            {
                "case_id": "case-2",
                "passed": False,
                "failures": ["expected_event_match"],
            },
        ]
        self.assertEqual(
            qualification._qualification_outcome(case_reports),
            "NOT_QUALIFIED",
        )


if __name__ == "__main__":
    unittest.main()
