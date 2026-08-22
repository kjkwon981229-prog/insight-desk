from __future__ import annotations

import unittest
from datetime import datetime, timezone

from insight_desk.core import (
    Certainty,
    FailureKind,
    OutcomePolarity,
    RawArticle,
    SourceProvenance,
    TemporalState,
)
from insight_desk.providers import GROQ_20B, GROQ_120B, ProviderTransportError
from insight_desk.semantic import EvidenceSegmenter, FactExtractionRequest
from insight_desk.semantic.groq_extractor import FACT_EXTRACTION_SCHEMA, Groq20BFactExtractor


NOW = datetime(2026, 8, 23, 4, 0, tzinfo=timezone.utc)


def make_request(body: str = "12일 서울에서 열릴 한화와 두산 경기가 폭염으로 취소됐다."):
    article = RawArticle(
        article_id="article-groq-extractor-test",
        provenance=SourceProvenance(
            source_id="fixture:test",
            source_name="fixture",
            url="https://example.invalid/test",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="테스트 기사",
        body=body,
        topic_ids=("kbo_hanwha",),
        query="프로야구",
    )
    evidence = EvidenceSegmenter().segment(article)
    return FactExtractionRequest(article=article, topic_id="kbo_hanwha", evidence=evidence)


class FakeGroqClient:
    def __init__(self, response, *, model_id=GROQ_20B):
        self.model_id = model_id
        self.response = response
        self.calls = []

    def structured_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def valid_fact(evidence_id: str) -> dict:
    return {
        "subject": "한화와 두산 경기",
        "action": "취소",
        "object": None,
        "temporal_state": "cancelled",
        "certainty": "asserted",
        "polarity": "negative",
        "event_date": "12일",
        "location": "서울",
        "cause": "폭염",
        "participants": ["한화", "두산"],
        "evidence_ids": [evidence_id],
    }


class Groq20BFactExtractorTests(unittest.TestCase):
    def test_valid_fact_is_mapped_to_untrusted_draft(self):
        request = make_request()
        evidence_id = request.evidence[0].evidence_id
        client = FakeGroqClient({"facts": [valid_fact(evidence_id)]})
        drafts = Groq20BFactExtractor(client).extract(request)
        self.assertEqual(len(drafts), 1)
        draft = drafts[0]
        self.assertEqual(draft.subject, "한화와 두산 경기")
        self.assertEqual(draft.action, "취소")
        self.assertIs(draft.temporal_state, TemporalState.CANCELLED)
        self.assertIs(draft.certainty, Certainty.ASSERTED)
        self.assertIs(draft.polarity, OutcomePolarity.NEGATIVE)
        self.assertEqual(draft.event_date, "12일")
        self.assertEqual(draft.location, "서울")
        self.assertEqual(draft.cause, "폭염")
        self.assertEqual(draft.participants, ("한화", "두산"))
        self.assertEqual(draft.evidence_ids, (evidence_id,))
        self.assertEqual(client.calls[0]["schema_name"], "insight_desk_fact_extract_v1")
        self.assertIn(evidence_id, client.calls[0]["prompt"])
        self.assertIn(request.evidence[0].text, client.calls[0]["prompt"])

    def test_subject_normalization_is_allowed_only_as_unverified_draft(self):
        request = make_request()
        evidence_id = request.evidence[0].evidence_id
        fact = valid_fact(evidence_id)
        fact["subject"] = "한화-두산 경기"
        drafts = Groq20BFactExtractor(FakeGroqClient({"facts": [fact]})).extract(request)
        self.assertEqual(drafts[0].subject, "한화-두산 경기")
        self.assertEqual(drafts[0].evidence_ids, (evidence_id,))

    def test_empty_fact_array_is_valid_fail_closed_result(self):
        request = make_request("원·달러 환율 1417.53원")
        client = FakeGroqClient({"facts": []})
        self.assertEqual(Groq20BFactExtractor(client).extract(request), ())

    def test_foreign_evidence_id_is_rejected(self):
        request = make_request()
        fact = valid_fact("ev:foreign:0001")
        with self.assertRaises(ProviderTransportError) as raised:
            Groq20BFactExtractor(FakeGroqClient({"facts": [fact]})).extract(request)
        self.assertIs(raised.exception.failure_kind, FailureKind.INVALID_OUTPUT)
        self.assertIn("outside extraction request", raised.exception.detail)

    def test_non_literal_object_is_rejected(self):
        request = make_request()
        evidence_id = request.evidence[0].evidence_id
        fact = valid_fact(evidence_id)
        fact["object"] = "선발투수 왕옌청"
        with self.assertRaises(ProviderTransportError) as raised:
            Groq20BFactExtractor(FakeGroqClient({"facts": [fact]})).extract(request)
        self.assertIs(raised.exception.failure_kind, FailureKind.INVALID_OUTPUT)
        self.assertIn("object is not source-literal", raised.exception.detail)

    def test_non_literal_participant_is_rejected(self):
        request = make_request()
        evidence_id = request.evidence[0].evidence_id
        fact = valid_fact(evidence_id)
        fact["participants"] = ["기아"]
        with self.assertRaises(ProviderTransportError) as raised:
            Groq20BFactExtractor(FakeGroqClient({"facts": [fact]})).extract(request)
        self.assertIs(raised.exception.failure_kind, FailureKind.INVALID_OUTPUT)
        self.assertIn("participant is not source-literal", raised.exception.detail)

    def test_duplicate_semantic_draft_is_rejected(self):
        request = make_request()
        evidence_id = request.evidence[0].evidence_id
        fact = valid_fact(evidence_id)
        client = FakeGroqClient({"facts": [dict(fact), dict(fact)]})
        with self.assertRaises(ProviderTransportError) as raised:
            Groq20BFactExtractor(client).extract(request)
        self.assertIn("duplicate semantic draft", raised.exception.detail)

    def test_extractor_is_frozen_to_20b(self):
        with self.assertRaisesRegex(ValueError, "frozen to Groq GPT-OSS 20B"):
            Groq20BFactExtractor(FakeGroqClient({"facts": []}, model_id=GROQ_120B))

    def test_schema_is_closed_at_root_and_fact_item(self):
        self.assertFalse(FACT_EXTRACTION_SCHEMA["additionalProperties"])
        self.assertEqual(FACT_EXTRACTION_SCHEMA["required"], ["facts"])
        item = FACT_EXTRACTION_SCHEMA["properties"]["facts"]["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(set(item["required"]), set(item["properties"]))


if __name__ == "__main__":
    unittest.main()
