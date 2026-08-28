from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import EVENT_UNDERSTANDING_SCHEMA_V2
from insight_desk.event_understanding_adapter_v3 import (
    EVENT_UNDERSTANDING_SCHEMA_V3,
    EventUnderstandingAdapterError,
    StructuredJsonEventUnderstandingAdapterV3,
)
from scripts import qualify_event_understanding_provider as historical_v3
from scripts import qualify_event_understanding_provider_v4 as qualification_v4


class _StaticStructuredClient:
    model_id = "fixture-observability"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def structured_json(self, **_: object) -> dict[str, object]:
        return deepcopy(self.payload)


class EventUnderstandingContractObservabilityV4Tests(unittest.TestCase):
    @staticmethod
    def _request() -> EventUnderstandingRequest:
        body = "한국은행은 기준금리를 결정했다."
        source = SourceDocument(
            source_id="source-1",
            candidate_ids=("candidate-1",),
            publisher="fixture",
            url="https://example.com/article",
            title="한국은행 기준금리 결정",
            body=body,
            fetched_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
            publication_time=None,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )
        return EventUnderstandingRequest(
            topic="macro",
            semantic_scope="한국은행 통화정책",
            sources=(source,),
        )

    @staticmethod
    def _payload(**event_overrides: object) -> dict[str, object]:
        event: dict[str, object] = {
            "article_role": "primary",
            "topic_relation": "direct",
            "understanding_status": "resolved",
            "actor": "한국은행",
            "action": "결정",
            "object": "기준금리",
            "event_type": "rate_decision",
            "event_time": "",
            "participants": [],
            "metric": "",
            "unit": "",
            "value": "",
            "attribution": "",
            "parent_event_hint": "",
            "uncertainty_reasons": [],
            "evidence": [
                {
                    "source_id": "source-1",
                    "field": "body",
                    "text": "한국은행은 기준금리를 결정했다.",
                }
            ],
        }
        event.update(event_overrides)
        return {
            "status": "resolved",
            "uncertainty_reasons": [],
            "events": [event],
        }

    def _adapter(self, payload: dict[str, object]) -> StructuredJsonEventUnderstandingAdapterV3:
        return StructuredJsonEventUnderstandingAdapterV3(
            client=_StaticStructuredClient(payload),
            engine_id="qualification-v4:fixture-observability",
        )

    def _failure(self, **event_overrides: object) -> EventUnderstandingAdapterError:
        with self.assertRaises(EventUnderstandingAdapterError) as caught:
            self._adapter(self._payload(**event_overrides)).understand(self._request())
        self.assertEqual(caught.exception.failure_code, "event_draft_contract")
        return caught.exception

    def test_provider_output_reachable_event_draft_invariants_have_stable_detail_codes(self) -> None:
        duplicate_evidence = [
            {
                "source_id": "source-1",
                "field": "body",
                "text": "한국은행은 기준금리를 결정했다.",
            },
            {
                "source_id": "source-1",
                "field": "body",
                "text": "한국은행은 기준금리를 결정했다.",
            },
        ]
        cases = (
            ({"evidence": duplicate_evidence}, "duplicate_evidence_refs"),
            ({"participants": ["한국은행", "한국은행"]}, "duplicate_participants"),
            (
                {"uncertainty_reasons": ["same", "same"]},
                "duplicate_event_uncertainty_reasons",
            ),
            ({"event_time": "not-an-iso-date"}, "event_time_format"),
            ({"event_time": "2026-08-28T12:00:00"}, "event_time_timezone"),
            ({"value": "3.50"}, "value_requires_metric"),
            ({"metric": "rate"}, "metric_requires_value"),
            (
                {"uncertainty_reasons": ["fixture uncertainty"]},
                "resolved_event_with_uncertainty",
            ),
            (
                {"understanding_status": "unresolved"},
                "unresolved_event_without_uncertainty",
            ),
        )

        observed: set[str] = set()
        for overrides, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                failure = self._failure(**overrides)
                self.assertEqual(failure.diagnostic_code, expected_code)
                observed.add(failure.diagnostic_code)
        self.assertEqual(len(observed), len(cases))

    def test_article_understanding_contract_also_keeps_bounded_detail_code(self) -> None:
        payload = self._payload()
        payload["uncertainty_reasons"] = ["fixture uncertainty"]
        with self.assertRaises(EventUnderstandingAdapterError) as caught:
            self._adapter(payload).understand(self._request())
        self.assertEqual(caught.exception.failure_code, "article_understanding_contract")
        self.assertEqual(
            caught.exception.diagnostic_code,
            "resolved_article_with_uncertainty",
        )

    def test_v4_reporter_adds_detail_without_changing_primary_failure_code(self) -> None:
        failure = self._failure(value="3.50")
        self.assertEqual(
            qualification_v4._adapter_failures(failure),
            [
                "adapter_contract:event_draft_contract",
                "adapter_detail:value_requires_metric",
            ],
        )
        self.assertEqual(
            historical_v3._qualification_failure_codes(failure),
            ["adapter_contract:event_draft_contract"],
        )

    def test_v4_reporter_preserves_generic_behavior_when_no_detail_exists(self) -> None:
        failure = EventUnderstandingAdapterError(
            "bounded fixture",
            failure_code="evidence_contract",
        )
        self.assertEqual(
            qualification_v4._adapter_failures(failure),
            ["adapter_contract:evidence_contract"],
        )

    def test_observability_does_not_change_v4_structured_output_schema(self) -> None:
        self.assertEqual(
            EVENT_UNDERSTANDING_SCHEMA_V3["properties"]["events"]["items"]["properties"],
            {
                **EVENT_UNDERSTANDING_SCHEMA_V2["properties"]["events"]["items"]["properties"],
                "evidence": EVENT_UNDERSTANDING_SCHEMA_V3["properties"]["events"]["items"]["properties"]["evidence"],
            },
        )
        evidence = EVENT_UNDERSTANDING_SCHEMA_V3["properties"]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id", "field", "text"])
        self.assertNotIn("start", evidence["properties"])
        self.assertNotIn("end", evidence["properties"])


if __name__ == "__main__":
    unittest.main()
