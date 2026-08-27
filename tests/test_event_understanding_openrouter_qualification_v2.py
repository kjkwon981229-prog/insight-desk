from __future__ import annotations

import unittest

from insight_desk.providers.openrouter import (
    OPENROUTER_NEMOTRON_3_SUPER_FREE,
    OpenRouterNemotronStructuredClient,
)
from scripts import qualify_event_understanding_provider as qualification


class EventUnderstandingOpenRouterQualificationHarnessTests(unittest.TestCase):
    def test_openrouter_candidate_remains_registered_under_active_v2_protocol(self) -> None:
        self.assertIn("openrouter_nemotron", qualification.PROVIDER_CHOICES)
        self.assertEqual(
            qualification._provider_model("openrouter_nemotron"),
            OPENROUTER_NEMOTRON_3_SUPER_FREE,
        )
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v2.json",
        )
        self.assertEqual(qualification.DEFAULT_SCOPES.name, "semantic_topics_v2.json")

    def test_missing_openrouter_key_is_preflight_not_semantic_failure(self) -> None:
        self.assertFalse(OpenRouterNemotronStructuredClient.configured({}))


if __name__ == "__main__":
    unittest.main()
