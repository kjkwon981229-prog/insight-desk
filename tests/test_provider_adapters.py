import io
import json
import unittest
import urllib.error
from email.message import Message

from insight_desk.core import FailureKind, TemporalState
from insight_desk.providers import (
    GROQ_20B,
    GROQ_120B,
    CloudflareClaimVerifier,
    GroqFreeClient,
    JsonHttpTransport,
    LocalNliVerifier,
    ProviderTransportError,
)


STRICT_SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "string"}},
    "required": ["value"],
    "additionalProperties": False,
}


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


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ProviderAdapterTests(unittest.TestCase):
    def test_transport_sets_api_headers_and_decodes_object(self):
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({"ok": True})

        transport = JsonHttpTransport(opener=opener, sleeper=lambda _: None)
        result = transport.post_json("https://example.invalid", {"x": 1}, {"X-Test": "yes"})
        request = captured["request"]
        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.get_header("User-agent"), "insight-desk/0.4")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("X-test"), "yes")
        self.assertEqual(captured["timeout"], 90)

    def test_transport_classifies_429_as_free_quota_exhaustion(self):
        headers = Message()
        error = urllib.error.HTTPError(
            "https://example.invalid",
            429,
            "Too Many Requests",
            headers,
            io.BytesIO(b"free quota exceeded"),
        )

        def opener(request, timeout):
            raise error

        transport = JsonHttpTransport(attempts=1, opener=opener, sleeper=lambda _: None)
        with self.assertRaises(ProviderTransportError) as raised:
            transport.post_json("https://example.invalid", {}, {})
        self.assertIs(raised.exception.failure_kind, FailureKind.FREE_QUOTA_EXHAUSTED)
        self.assertEqual(raised.exception.status_code, 429)

    def test_cloudflare_success_maps_to_verification_check(self):
        transport = RecordingTransport(
            {"success": True, "result": {"response": '{"entailed": true}'}}
        )
        verifier = CloudflareClaimVerifier("account", "token", transport)
        check = verifier.verify(
            check_id="c1",
            claim_text="9월 3일부터 시행한다.",
            evidence_text="공식 발표에 따르면 9월 3일부터 시행한다.",
            evidence_ids=("e1",),
        )
        self.assertTrue(check.entailed)
        self.assertEqual(check.verifier_id, "cloudflare")
        self.assertTrue(check.zero_cost)
        _, payload, headers = transport.calls[0]
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(headers["Authorization"], "Bearer token")

    def test_cloudflare_provider_failure_becomes_inconclusive_check(self):
        transport = RecordingTransport(
            error=ProviderTransportError(
                failure_kind=FailureKind.FREE_QUOTA_EXHAUSTED,
                status_code=429,
            )
        )
        verifier = CloudflareClaimVerifier("account", "token", transport)
        check = verifier.verify(
            check_id="c1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("e1",),
        )
        self.assertIsNone(check.entailed)
        self.assertEqual(check.error_code, "free_quota_exhausted:429")

    def test_local_nli_wraps_boolean_and_failure(self):
        supported = LocalNliVerifier(lambda premise, hypothesis: True).verify(
            check_id="local-1",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("e1",),
        )
        self.assertTrue(supported.entailed)
        self.assertEqual(supported.verifier_id, "local-nli")

        def broken(premise, hypothesis):
            raise RuntimeError("model unavailable")

        failed = LocalNliVerifier(broken).verify(
            check_id="local-2",
            claim_text="claim",
            evidence_text="evidence",
            evidence_ids=("e1",),
        )
        self.assertIsNone(failed.entailed)
        self.assertTrue(failed.error_code.startswith("local_model_error:"))

    def test_groq_client_rejects_models_outside_frozen_allowlist(self):
        with self.assertRaises(ValueError):
            GroqFreeClient("key", "some-paid-or-unknown-model", RecordingTransport())

    def test_groq_structured_payload_is_strict_and_low_reasoning(self):
        transport = RecordingTransport(
            {"choices": [{"message": {"content": '{"value":"ok"}'}}]}
        )
        client = GroqFreeClient("key", GROQ_20B, transport, delay_seconds=0)
        result = client.structured_json(
            prompt="return value",
            schema=STRICT_SCHEMA,
            schema_name="test_schema",
        )
        self.assertEqual(result, {"value": "ok"})
        _, payload, headers = transport.calls[0]
        self.assertEqual(payload["model"], GROQ_20B)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(headers["Authorization"], "Bearer key")

    def test_groq_rejects_non_strict_schema_before_provider_call(self):
        transport = RecordingTransport()
        client = GroqFreeClient("key", GROQ_20B, transport, delay_seconds=0)
        with self.assertRaises(ValueError):
            client.structured_json(
                prompt="x",
                schema={"type": "object", "properties": {"x": {"type": "string"}}},
                schema_name="bad",
            )
        self.assertEqual(transport.calls, [])

    def test_temporal_auxiliary_is_frozen_to_120b_and_contract_enum(self):
        transport = RecordingTransport(
            {
                "choices": [
                    {"message": {"content": '{"temporal_state":"announced_prospective"}'}}
                ]
            }
        )
        client = GroqFreeClient("key", GROQ_120B, transport, delay_seconds=0)
        self.assertIs(
            client.classify_temporal("9월부터 시행한다고 밝혔다."),
            TemporalState.ANNOUNCED_PROSPECTIVE,
        )

        client20 = GroqFreeClient("key", GROQ_20B, RecordingTransport(), delay_seconds=0)
        with self.assertRaises(ValueError):
            client20.classify_temporal("9월부터 시행한다고 밝혔다.")


if __name__ == "__main__":
    unittest.main()
