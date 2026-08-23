from __future__ import annotations

import unittest

from insight_desk.core import VerificationCheck
from insight_desk.providers.gemini import (
    GEMINI_FLASH_LITE,
    GEMINI_VERIFIER_ID,
    GeminiClaimVerifier,
    GeminiStructuredClient,
)
from insight_desk.providers.local_nli import (
    LOCAL_NLI_FALLBACK_MODEL,
    LOCAL_NLI_FALLBACK_ROUTE_ID,
    LazyLocalNliVerifier,
)


class RecordingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class Phase12BGeminiContractTests(unittest.TestCase):
    def test_gemini_route_is_optional_without_key(self) -> None:
        self.assertFalse(GeminiStructuredClient.configured({}))
        self.assertTrue(GeminiStructuredClient.configured({"GEMINI_API_KEY": "configured"}))

    def test_gemini_structured_json_uses_stable_flash_lite_and_schema(self) -> None:
        transport = RecordingTransport(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '{"entailed":true}'}
                            ]
                        }
                    }
                ]
            }
        )
        client = GeminiStructuredClient("key", transport=transport)
        result = client.structured_json(
            prompt="claim",
            schema={
                "type": "object",
                "properties": {"entailed": {"type": "boolean"}},
                "required": ["entailed"],
                "additionalProperties": False,
            },
            schema_name="test",
        )
        self.assertEqual(result, {"entailed": True})
        url, payload, headers = transport.calls[0]
        self.assertIn(GEMINI_FLASH_LITE, url)
        self.assertEqual(headers["x-goog-api-key"], "key")
        response_format = payload["generationConfig"]["responseFormat"]["text"]
        self.assertEqual(response_format["mimeType"], "application/json")
        self.assertEqual(response_format["schema"]["required"], ["entailed"])

    def test_gemini_claim_verifier_preserves_boolean_contract(self) -> None:
        transport = RecordingTransport(
            {
                "candidates": [
                    {"content": {"parts": [{"text": '{"entailed":false}'}]}}
                ]
            }
        )
        verifier = GeminiClaimVerifier(GeminiStructuredClient("key", transport=transport))
        check = verifier.verify(
            check_id="gemini:1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertFalse(check.entailed)
        self.assertEqual(check.verifier_id, GEMINI_VERIFIER_ID)
        self.assertEqual(check.model_id, GEMINI_FLASH_LITE)


class Phase12BLocalFallbackContractTests(unittest.TestCase):
    def test_minilm_fallback_is_lazy_and_not_loaded_during_construction(self) -> None:
        verifier = LazyLocalNliVerifier()
        self.assertEqual(verifier.model_id, LOCAL_NLI_FALLBACK_MODEL)
        self.assertEqual(verifier.verifier_id, LOCAL_NLI_FALLBACK_ROUTE_ID)
        self.assertIsNone(verifier._delegate)

    def test_local_fallback_route_has_independent_route_identity(self) -> None:
        verifier = LazyLocalNliVerifier()
        self.assertNotEqual(verifier.verifier_id, "local-nli")
        self.assertIn("MiniLM", verifier.model_id)


if __name__ == "__main__":
    unittest.main()
