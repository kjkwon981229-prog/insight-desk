from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import (
    EventUnderstandingAdapterError,
    StructuredJsonEventUnderstandingAdapter,
)


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
BODY = "한국은행 금융통화위원회는 기준금리를 유지했다."
SCOPE = "Current monetary-policy events where the policy decision is the actual event."


def source() -> SourceDocument:
    return SourceDocument(
        source_id="source:1",
        candidate_ids=("candidate:1",),
        publisher="example",
        url="https://example.com/article",
        title="한국은행 기준금리 결정",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


def response(*, evidence_text: str = BODY) -> dict[str, object]:
    return {
        "status": "resolved",
        "uncertainty_reasons": [],
        "events": [
            {
                "article_role": "primary",
                "topic_relation": "direct",
                "understanding_status": "resolved",
                "actor": "한국은행 금융통화위원회",
                "action": "기준금리를 유지했다",
                "object": "기준금리",
                "event_type": "rate_decision",
                "event_time": "",
                "participants": [],
                "metric": "",
                "unit": "",
                "value": "",
                "attribution": "한국은행 금융통화위원회",
                "parent_event_hint": "금융통화위원회 회의",
                "uncertainty_reasons": [],
                "evidence": [
                    {
                        "source_id": "source:1",
                        "field": "body",
                        "text": evidence_text,
                        "start": 0,
                        "end": len(BODY),
                    }
                ],
            }
        ],
    }


class _FakeStructuredClient:
    model_id = "fake-model"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.last_prompt = ""

    def structured_json(self, *, prompt, schema, schema_name, system_prompt):
        self.calls += 1
        self.last_prompt = prompt
        self.schema = schema
        self.schema_name = schema_name
        self.system_prompt = system_prompt
        return self.payload


class StructuredJsonEventUnderstandingAdapterTests(unittest.TestCase):
    def test_exact_source_evidence_is_converted_to_offset_and_digest(self) -> None:
        src = source()
        client = _FakeStructuredClient(response())
        adapter = StructuredJsonEventUnderstandingAdapter(client, "fake-engine")
        result = adapter.understand(
            EventUnderstandingRequest(topic="economy", semantic_scope=SCOPE, sources=(src,))
        )
        self.assertEqual(client.calls, 1)
        self.assertEqual(len(result.event_drafts), 1)
        ref = result.event_drafts[0].evidence_refs[0]
        self.assertEqual(ref.start, 0)
        self.assertEqual(ref.end, len(BODY))
        ref.validate_against(src)
        self.assertNotIn("intent_anchors", client.last_prompt)
        self.assertNotIn("required_intent_terms", client.last_prompt)

    def test_paraphrased_evidence_is_rejected_not_fuzzily_matched(self) -> None:
        src = source()
        client = _FakeStructuredClient(response(evidence_text="한국은행은 기준금리를 유지했다."))
        adapter = StructuredJsonEventUnderstandingAdapter(client, "fake-engine")
        with self.assertRaisesRegex(EventUnderstandingAdapterError, "exact source substring"):
            adapter.understand(
                EventUnderstandingRequest(topic="economy", semantic_scope=SCOPE, sources=(src,))
            )

    def test_adapter_generates_provisional_id_instead_of_accepting_model_identity(self) -> None:
        src = source()
        adapter = StructuredJsonEventUnderstandingAdapter(_FakeStructuredClient(response()), "fake-engine")
        result = adapter.understand(
            EventUnderstandingRequest(topic="economy", semantic_scope=SCOPE, sources=(src,))
        )
        self.assertTrue(result.event_drafts[0].draft_id.startswith("event-draft:"))
        self.assertNotIn("event_id", response()["events"][0])


if __name__ == "__main__":
    unittest.main()
