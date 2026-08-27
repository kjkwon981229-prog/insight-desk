from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import (
    EventUnderstandingAdapterError,
    StructuredJsonEventUnderstandingAdapter,
)
from scripts import qualify_event_understanding_provider as qualification


NOW = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
BODY = "한국은행은 27일 기준금리를 결정한다."


def source() -> SourceDocument:
    return SourceDocument(
        source_id="source:diagnostic",
        candidate_ids=("candidate:diagnostic",),
        publisher="example-news",
        url="https://example.com/diagnostic",
        title="한국은행 기준금리 결정",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


class _FakeClient:
    model_id = "fake-diagnostic"

    def structured_json(self, *, prompt, schema, schema_name, system_prompt):
        return {
            "status": "resolved",
            "uncertainty_reasons": [],
            "events": [
                {
                    "article_role": "primary",
                    "topic_relation": "direct",
                    "understanding_status": "resolved",
                    "actor": "한국은행",
                    "action": "기준금리를 결정한다",
                    "object": "기준금리",
                    "event_type": "rate_decision",
                    "event_time": "27일",
                    "participants": [],
                    "metric": "",
                    "unit": "",
                    "value": "",
                    "attribution": "한국은행",
                    "parent_event_hint": "",
                    "uncertainty_reasons": [],
                    "evidence": [
                        {
                            "source_id": "source:diagnostic",
                            "field": "body",
                            "text": BODY,
                            "start": 0,
                            "end": len(BODY),
                        }
                    ],
                }
            ],
        }


class EventUnderstandingFailureObservabilityV3Tests(unittest.TestCase):
    def test_core_contract_failure_is_wrapped_as_safe_stage_code(self) -> None:
        adapter = StructuredJsonEventUnderstandingAdapter(_FakeClient(), "fake-diagnostic")
        with self.assertRaises(EventUnderstandingAdapterError) as caught:
            adapter.understand(
                EventUnderstandingRequest(
                    topic="economy",
                    semantic_scope="Current monetary-policy events.",
                    sources=(source(),),
                )
            )
        self.assertEqual(caught.exception.failure_code, "event_draft_contract")
        codes = qualification._qualification_failure_codes(caught.exception)
        self.assertEqual(codes, ["adapter_contract:event_draft_contract"])
        rendered = "\n".join(codes)
        self.assertNotIn(BODY, rendered)
        self.assertNotIn("27일", rendered)


if __name__ == "__main__":
    unittest.main()
