from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import StructuredJsonEventUnderstandingAdapter


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
SENTENCE = "한국은행은 기준금리를 동결했다."
BODY = f"{SENTENCE} {SENTENCE}"
SECOND_START = len(SENTENCE) + 1


class _FakeStructuredClient:
    model_id = "fake-range-engine"

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
                    "action": "기준금리를 동결했다",
                    "object": "기준금리",
                    "event_type": "rate_decision",
                    "event_time": "",
                    "participants": [],
                    "metric": "",
                    "unit": "",
                    "value": "",
                    "attribution": "한국은행",
                    "parent_event_hint": "",
                    "uncertainty_reasons": [],
                    "evidence": [
                        {
                            "source_id": "source:duplicate-evidence",
                            "field": "body",
                            "text": SENTENCE,
                            "start": SECOND_START,
                            "end": SECOND_START + len(SENTENCE),
                        }
                    ],
                }
            ],
        }


class EventUnderstandingEvidenceRangeHandoffV2Tests(unittest.TestCase):
    def test_semantic_owner_can_disambiguate_repeated_exact_evidence_with_range(self) -> None:
        source = SourceDocument(
            source_id="source:duplicate-evidence",
            candidate_ids=("candidate:duplicate-evidence",),
            publisher="example-news",
            url="https://example.com/duplicate-evidence",
            title="한국은행 기준금리 동결",
            body=BODY,
            fetched_at=NOW,
            publication_time=NOW,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
        )
        result = StructuredJsonEventUnderstandingAdapter(
            _FakeStructuredClient(), "fake-range-engine"
        ).understand(
            EventUnderstandingRequest(
                topic="economy",
                semantic_scope="Current monetary-policy events.",
                sources=(source,),
            )
        )
        ref = result.event_drafts[0].evidence_refs[0]
        self.assertEqual(ref.start, SECOND_START)
        self.assertEqual(ref.end, SECOND_START + len(SENTENCE))
        ref.validate_against(source)


if __name__ == "__main__":
    unittest.main()
