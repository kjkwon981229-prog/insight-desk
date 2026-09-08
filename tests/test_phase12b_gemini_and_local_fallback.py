from __future__ import annotations

import unittest

from insight_desk.core import FailureKind
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID, CloudflareClaimVerifier
from insight_desk.providers.gemini import (
    GEMINI_FLASH_LITE,
    GEMINI_INTERACTIONS_URL,
    GEMINI_VERIFIER_ID,
    GeminiClaimVerifier,
    GeminiStructuredClient,
)
from insight_desk.providers.resilience import FailoverClaimVerifier
from insight_desk.providers.transport import ProviderTransportError


class RecordingTransport:
    def __init__(self, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.calls = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        if self.error is not None:
            raise self.error
        return self.response


def interaction(text: str) -> dict[str, object]:
    return {
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


class Phase12BGeminiContractTests(unittest.TestCase):
    def test_gemini_route_is_optional_without_key(self) -> None:
        self.assertFalse(GeminiStructuredClient.configured({}))
        self.assertTrue(GeminiStructuredClient.configured({"GEMINI_API_KEY": "configured"}))

    def test_gemini_structured_json_uses_current_interactions_contract(self) -> None:
        transport = RecordingTransport(interaction('{"entailed":true}'))
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
        self.assertEqual(url, GEMINI_INTERACTIONS_URL)
        self.assertEqual(payload["model"], GEMINI_FLASH_LITE)
        self.assertEqual(headers["x-goog-api-key"], "key")
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "text")
        self.assertEqual(response_format["mime_type"], "application/json")
        self.assertEqual(response_format["schema"]["required"], ["entailed"])

    def test_gemini_claim_verifier_preserves_boolean_contract(self) -> None:
        transport = RecordingTransport(interaction('{"entailed":false}'))
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

    def test_cloudflare_factory_without_gemini_still_has_run_local_circuit(self) -> None:
        verifier = CloudflareClaimVerifier.from_env(
            env={
                "CLOUDFLARE_ACCOUNT_ID": "account",
                "CLOUDFLARE_API_TOKEN": "token",
            },
            transport=RecordingTransport(
                error=ProviderTransportError(
                    failure_kind=FailureKind.RATE_LIMITED,
                    status_code=429,
                    detail='{"errors":[{"code":3036,"message":"daily free allocation"}]}',
                )
            ),
        )
        self.assertIsInstance(verifier, FailoverClaimVerifier)
        self.assertEqual(verifier.verifier_id, CLOUDFLARE_VERIFIER_ID)
        self.assertEqual(len(verifier.routes), 1)
        first = verifier.verify(
            check_id="cf:1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        second = verifier.verify(
            check_id="cf:2",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertIsNone(first.entailed)
        self.assertIsNone(second.entailed)
        self.assertEqual(verifier.routes[0].transport.calls.__len__(), 1)

    def test_cloudflare_factory_fails_over_to_gemini_when_configured(self) -> None:
        cloudflare_transport = RecordingTransport(
            error=ProviderTransportError(
                failure_kind=FailureKind.RATE_LIMITED,
                status_code=429,
                detail='{"errors":[{"code":3036,"message":"daily free allocation"}]}',
            )
        )
        gemini_transport = RecordingTransport(interaction('{"entailed":true}'))
        verifier = CloudflareClaimVerifier.from_env(
            env={
                "CLOUDFLARE_ACCOUNT_ID": "account",
                "CLOUDFLARE_API_TOKEN": "token",
                "GEMINI_API_KEY": "gemini-key",
            },
            transport=cloudflare_transport,
            gemini_transport=gemini_transport,
        )
        self.assertIsInstance(verifier, FailoverClaimVerifier)
        self.assertEqual(verifier.verifier_id, CLOUDFLARE_VERIFIER_ID)
        self.assertEqual(len(verifier.routes), 2)
        first = verifier.verify(
            check_id="slot:1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        second = verifier.verify(
            check_id="slot:2",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("ev:1",),
        )
        self.assertTrue(first.entailed)
        self.assertTrue(second.entailed)
        self.assertEqual(first.verifier_id, CLOUDFLARE_VERIFIER_ID)
        self.assertEqual(first.model_id, GEMINI_FLASH_LITE)
        self.assertEqual(len(cloudflare_transport.calls), 1)
        self.assertEqual(len(gemini_transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
