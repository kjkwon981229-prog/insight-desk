from __future__ import annotations

from pathlib import Path
import unittest


class NoGeneratedTextIdentityAuthorityTests(unittest.TestCase):
    def test_daily_production_has_no_headline_or_summary_identity_gate(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")

        for forbidden in (
            "published_headline_keys",
            "published_summary_keys",
            "normalized_headline_already_published",
            "normalized_summary_already_published",
        ):
            self.assertNotIn(forbidden, source)

    def test_canonical_identity_still_runs_before_publication(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        identity_position = source.index("compare_candidate_identity(event, prior_event, identity_facts)")
        publish_position = source.index("published.append(")
        self.assertLess(identity_position, publish_position)


if __name__ == "__main__":
    unittest.main()
