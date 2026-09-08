from __future__ import annotations

import unittest

from insight_desk.providers.mistral import MISTRAL_LARGE_3, MistralStructuredClient
from scripts import qualify_event_understanding_provider as qualification


class EventUnderstandingMistralQualificationHarnessTests(unittest.TestCase):
    def test_mistral_candidate_remains_registered_under_active_v3_protocol(self) -> None:
        self.assertIn("mistral", qualification.PROVIDER_CHOICES)
        self.assertEqual(qualification._provider_model("mistral"), MISTRAL_LARGE_3)
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v3.json",
        )
        self.assertEqual(qualification.DEFAULT_SCOPES.name, "semantic_topics_v2.json")

    def test_missing_mistral_key_is_preflight_not_semantic_failure(self) -> None:
        self.assertFalse(MistralStructuredClient.configured({}))


if __name__ == "__main__":
    unittest.main()
