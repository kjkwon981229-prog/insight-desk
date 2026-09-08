from __future__ import annotations

import unittest

from scripts.phase11_daily_production_core import (
    RELEVANCE_RESOLUTION_ACQUISITION_LIMIT,
    _candidate_budget_allows,
)


class RelevanceResolutionAcquisitionBudgetTests(unittest.TestCase):
    def test_resolution_candidate_remains_processable_after_normal_budget_is_exhausted(self) -> None:
        self.assertTrue(
            _candidate_budget_allows(
                candidate_url="https://example.test/resolution",
                relevance_resolution_candidate_urls={"https://example.test/resolution"},
                acquisition_attempts=8,
                max_acquisitions=8,
                relevance_resolution_acquisitions=0,
            )
        )

    def test_regular_candidate_stops_when_normal_budget_is_exhausted(self) -> None:
        self.assertFalse(
            _candidate_budget_allows(
                candidate_url="https://example.test/regular",
                relevance_resolution_candidate_urls={"https://example.test/resolution"},
                acquisition_attempts=8,
                max_acquisitions=8,
                relevance_resolution_acquisitions=0,
            )
        )

    def test_resolution_candidate_stops_at_its_own_bound(self) -> None:
        self.assertFalse(
            _candidate_budget_allows(
                candidate_url="https://example.test/resolution",
                relevance_resolution_candidate_urls={"https://example.test/resolution"},
                acquisition_attempts=8,
                max_acquisitions=8,
                relevance_resolution_acquisitions=RELEVANCE_RESOLUTION_ACQUISITION_LIMIT,
            )
        )


if __name__ == "__main__":
    unittest.main()
