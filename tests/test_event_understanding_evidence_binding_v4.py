from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
from datetime import datetime, timezone

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import EventUnderstandingAdapterError
from insight_desk.event_understanding_adapter_v3 import (
    EVENT_UNDERSTANDING_SCHEMA_V3,
    StructuredJsonEventUnderstandingAdapterV3,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
SCOPE = "Current monetary-policy events where the policy decision is the actual event."
BODY = "한국은행 금융통화위원회는 27일 회의를 열어 기준금리를 결정한다."
QUOTE = "기준금리를 결정한다"


def source(*, body: str = BODY) -> SourceDocument:
    return SourceDocument(
        source_id="source:1",
        candidate_ids=("candidate:1",),
        publisher="example",
        url="https://example.com/article",
        title="한국은행 금융통화위원회 기준금리 결정",
        body=body,
        fetched_at=NOW,
        publication_time=None,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def response(*, evidence_text: str = QUOTE) -> dict[str, object]:
    return {
        "status": "resolved",
        "uncertainty_reasons": [],
        "events": [
            {
                "article_role": "primary",
                "topic_relation": "direct",
                "understanding_status": "resolved",
                "actor": "한국은행 금융통화위원회",
                "action": "기준금리를 결정한다",
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
                    }
                ],
            }
        ],
    }


class _FakeStructuredClient:
    model_id = "fake-v4-model"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.schema = None
        self.prompt = ""

    def structured_json(self, *, prompt, schema, schema_name, system_prompt):
        self.calls += 1
        self.prompt = prompt
        self.schema = schema
        self.schema_name = schema_name
        self.system_prompt = system_prompt
        return self.payload


class EventUnderstandingEvidenceBindingV4Tests(unittest.TestCase):
    def test_unique_exact_quote_is_bound_deterministically_to_source_range(self) -> None:
        src = source()
        client = _FakeStructuredClient(response())
        adapter = StructuredJsonEventUnderstandingAdapterV3(client, "fake-v4-engine")
        result = adapter.understand(
            EventUnderstandingRequest(topic="economy", semantic_scope=SCOPE, sources=(src,))
        )

        ref = result.event_drafts[0].evidence_refs[0]
        expected_start = BODY.index(QUOTE)
        self.assertEqual(ref.start, expected_start)
        self.assertEqual(ref.end, expected_start + len(QUOTE))
        ref.validate_against(src)
        self.assertEqual(client.calls, 1)

    def test_provider_schema_does_not_assign_character_counting_to_semantic_owner(self) -> None:
        evidence_schema = EVENT_UNDERSTANDING_SCHEMA_V3["properties"]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(set(evidence_schema["required"]), {"source_id", "field", "text"})
        self.assertNotIn("start", evidence_schema["properties"])
        self.assertNotIn("end", evidence_schema["properties"])

    def test_paraphrased_quote_is_rejected_without_fuzzy_repair(self) -> None:
        adapter = StructuredJsonEventUnderstandingAdapterV3(
            _FakeStructuredClient(response(evidence_text="한국은행은 기준금리를 결정한다")),
            "fake-v4-engine",
        )
        with self.assertRaises(EventUnderstandingAdapterError) as caught:
            adapter.understand(
                EventUnderstandingRequest(topic="economy", semantic_scope=SCOPE, sources=(source(),))
            )
        self.assertEqual(caught.exception.failure_code, "evidence_contract")

    def test_duplicate_exact_quote_is_rejected_as_ambiguous(self) -> None:
        duplicate_body = f"{QUOTE}. 다른 설명. {QUOTE}."
        adapter = StructuredJsonEventUnderstandingAdapterV3(
            _FakeStructuredClient(response()),
            "fake-v4-engine",
        )
        with self.assertRaises(EventUnderstandingAdapterError) as caught:
            adapter.understand(
                EventUnderstandingRequest(
                    topic="economy",
                    semantic_scope=SCOPE,
                    sources=(source(body=duplicate_body),),
                )
            )
        self.assertEqual(caught.exception.failure_code, "evidence_contract")

    def test_v4_keeps_v3_semantic_gold_and_changes_only_evidence_handoff_metadata(self) -> None:
        v3 = json.loads(
            (ROOT / "tests/fixtures/event_understanding_qualification_v3.json").read_text(
                encoding="utf-8"
            )
        )
        v4 = json.loads(
            (ROOT / "tests/fixtures/event_understanding_qualification_v4.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(v4["schema_version"], 4)
        self.assertEqual(v4["core_contract"], v3["core_contract"])
        self.assertEqual(v4["cases"], v3["cases"])
        self.assertEqual(v4["acceptance"]["all_cases_must_pass"], True)
        self.assertEqual(v4["acceptance"]["exact_evidence_binding_required"], True)
        self.assertEqual(v4["structured_output_schema"], "event_understanding_schema_v3")


if __name__ == "__main__":
    unittest.main()
