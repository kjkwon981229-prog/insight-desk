from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.core.identity import (
    IdentityDecision,
    IdentityDisposition,
    identity_disposition,
)


class IdentityDispositionContractTests(unittest.TestCase):
    def test_unresolved_identity_is_defer_not_different_event(self) -> None:
        decision = IdentityDecision(
            same_event=None,
            deterministic_block=False,
            llm_judgment_used=False,
            reason="identity_unresolved",
        )
        self.assertEqual(identity_disposition(decision), IdentityDisposition.DEFER)

    def test_explicit_same_and_different_remain_distinct(self) -> None:
        same = IdentityDecision(
            same_event=True,
            deterministic_block=False,
            llm_judgment_used=True,
            reason="same",
        )
        different = IdentityDecision(
            same_event=False,
            deterministic_block=True,
            llm_judgment_used=False,
            reason="different",
        )
        self.assertEqual(identity_disposition(same), IdentityDisposition.SAME_EVENT)
        self.assertEqual(identity_disposition(different), IdentityDisposition.DIFFERENT_EVENT)

    def test_daily_production_consumes_identity_disposition_before_publication(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("identity_disposition(resolution.decision)", source)
        self.assertIn("IdentityDisposition.DEFER", source)
        self.assertIn('status="defer"', source)
        self.assertIn('reason="identity_unresolved"', source)


if __name__ == "__main__":
    unittest.main()
