from __future__ import annotations

import unittest

from insight_desk.core import TemporalState
from insight_desk.providers import GROQ_20B, GROQ_120B, GroqFreeClient


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return {
            "choices": [
                {"message": {"content": '{"temporal_state":"planned"}'}}
            ]
        }


class TemporalPromptContractTests(unittest.TestCase):
    def test_120b_temporal_prompt_defines_future_ongoing_completed_boundaries(self) -> None:
        transport = RecordingTransport()
        client = GroqFreeClient("key", GROQ_120B, transport, delay_seconds=0)

        self.assertIs(client.classify_temporal("A사가 27일 착공식을 연다."), TemporalState.PLANNED)

        _, payload, _ = transport.calls[0]
        self.assertEqual(payload["model"], GROQ_120B)
        prompt = payload["messages"][1]["content"]
        self.assertIn("planned:", prompt)
        self.assertIn("announced_prospective:", prompt)
        self.assertIn("resuming:", prompt)
        self.assertIn("resumed:", prompt)
        self.assertIn("ongoing:", prompt)
        self.assertIn("completed:", prompt)
        self.assertIn("cancelled:", prompt)
        self.assertIn("NEVER use ongoing for a simple future action", prompt)
        self.assertIn("simple past-completed action", prompt)
        self.assertIn("Use only the text; do not use external knowledge", prompt)
        self.assertIn("Preserve Korean tense/aspect exactly", prompt)

    def test_temporal_role_remains_frozen_to_120b(self) -> None:
        client = GroqFreeClient("key", GROQ_20B, RecordingTransport(), delay_seconds=0)
        with self.assertRaisesRegex(ValueError, "frozen to Groq 120B"):
            client.classify_temporal("A사가 27일 착공식을 연다.")


if __name__ == "__main__":
    unittest.main()
