from __future__ import annotations

from pathlib import Path
import unittest


class GeneratedTextIdentityAuthorityTests(unittest.TestCase):
    def test_daily_loop_does_not_use_generated_headline_or_summary_for_event_identity(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertNotIn("visible_event_redundant(", source)
        self.assertNotIn("visible_event_fingerprint_already_published", source)


if __name__ == "__main__":
    unittest.main()
