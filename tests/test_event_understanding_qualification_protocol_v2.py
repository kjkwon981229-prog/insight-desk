from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts import qualify_event_understanding_provider as qualification


ROOT = Path(__file__).resolve().parents[1]


class EventUnderstandingQualificationProtocolV2Tests(unittest.TestCase):
    def test_active_protocol_is_v2_and_does_not_score_free_text_by_literal_reproduction(self) -> None:
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v2.json",
        )
        payload = json.loads(
            qualification.DEFAULT_QUALIFICATION.read_text(encoding="utf-8")
        )
        for case in payload["cases"]:
            self.assertNotIn("required_structured_literals", case)
            self.assertTrue(case["expected_events"])
            for expected_event in case["expected_events"]:
                self.assertTrue(expected_event["required_evidence_literals"])
                self.assertIn("required_entity_literals", expected_event)


if __name__ == "__main__":
    unittest.main()
