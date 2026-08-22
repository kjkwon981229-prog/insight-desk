from __future__ import annotations

import unittest
from datetime import datetime, timezone

from insight_desk.core import (
    Certainty,
    OutcomePolarity,
    RawArticle,
    SourceProvenance,
    TemporalState,
)
from insight_desk.semantic import (
    EvidenceSegmenter,
    FactDraft,
    SemanticPipeline,
)

NOW = datetime(2026, 8, 23, 3, 0, tzinfo=timezone.utc)


def article(body: str, *, topics: tuple[str, ...] = ("ai_tech",)) -> RawArticle:
    return RawArticle(
        article_id="article-semantic-1",
        provenance=SourceProvenance(
            source_id="web:example.com",
            source_name="example.com",
            url="https://example.com/article",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="AI 규제안 9월 3일 시행 일정 발표",
        body=body,
        topic_ids=topics,
        query="AI 규제",
    )


class FakeExtractor:
    extractor_id = "fixture-fact-extractor"

    def __init__(self, drafts_factory) -> None:
        self.drafts_factory = drafts_factory
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        return self.drafts_factory(request)


class EvidenceSegmenterTests(unittest.TestCase):
    def test_all_evidence_is_exact_source_text(self) -> None:
        source = (
            "첫 문단은 9월 3일 시행 일정을 설명한다. " * 12
            + "\n\n"
            + "둘째 문단은 회사 측의 직접 인용과 13.6% 수치를 포함한다. " * 12
        )
        raw = article(source)
        spans = EvidenceSegmenter(max_chars=180).segment(raw)
        self.assertGreater(len(spans), 2)
        for span in spans:
            span.validate_against(raw)
            self.assertEqual(span.text, raw.body[span.start : span.end])
            self.assertLessEqual(len(span.text), 180)

    def test_evidence_ids_are_stable(self) -> None:
        raw = article("원문 본문입니다. " * 60)
        segmenter = EvidenceSegmenter(max_chars=160)
        left = segmenter.segment(raw)
        right = segmenter.segment(raw)
        self.assertEqual(
            [(item.evidence_id, item.start, item.end, item.text) for item in left],
            [(item.evidence_id, item.start, item.end, item.text) for item in right],
        )

    def test_whitespace_only_body_yields_no_evidence(self) -> None:
        raw = article("   \n\n   ")
        self.assertEqual(EvidenceSegmenter().segment(raw), ())


class SemanticPipelineTests(unittest.TestCase):
    def test_valid_fact_draft_becomes_one_fact_and_one_separate_candidate(self) -> None:
        raw = article("정부는 AI 규제안을 9월 3일부터 시행할 예정이라고 밝혔다. " * 20)

        def make_drafts(request):
            return (
                FactDraft(
                    draft_id="d1",
                    subject="정부",
                    action="시행 예정 발표",
                    object="AI 규제안",
                    evidence_ids=(request.evidence[0].evidence_id,),
                    temporal_state=TemporalState.ANNOUNCED_PROSPECTIVE,
                    certainty=Certainty.ASSERTED,
                    polarity=OutcomePolarity.NEUTRAL,
                    event_date="9월 3일",
                    participants=("정부",),
                ),
            )

        extractor = FakeExtractor(make_drafts)
        result = SemanticPipeline(segmenter=EvidenceSegmenter(max_chars=300)).extract_article(
            raw,
            topic_id="ai_tech",
            extractor=extractor,
        )
        self.assertEqual(result.extractor_id, "fixture-fact-extractor")
        self.assertEqual(len(result.facts), 1)
        self.assertEqual(len(result.events), 1)
        fact = result.facts[0]
        event = result.events[0]
        self.assertEqual(fact.subject, "정부")
        self.assertEqual(fact.event_date, "9월 3일")
        self.assertIs(fact.temporal_state, TemporalState.ANNOUNCED_PROSPECTIVE)
        self.assertEqual(event.fact_ids, (fact.fact_id,))
        self.assertEqual(event.article_ids, (raw.article_id,))
        self.assertEqual(event.topic_id, "ai_tech")
        self.assertIn(fact.evidence_ids[0], {span.evidence_id for span in result.evidence})

    def test_two_drafts_remain_two_candidate_events_before_identity_stage(self) -> None:
        raw = article("A사는 계획을 발표했다. B사는 별도 계약을 체결했다. " * 20)

        def make_drafts(request):
            evidence_id = request.evidence[0].evidence_id
            return (
                FactDraft("a", "A사", "계획 발표", (evidence_id,)),
                FactDraft("b", "B사", "계약 체결", (evidence_id,)),
            )

        result = SemanticPipeline().extract_article(
            raw,
            topic_id="ai_tech",
            extractor=FakeExtractor(make_drafts),
        )
        self.assertEqual(len(result.facts), 2)
        self.assertEqual(len(result.events), 2)
        self.assertNotEqual(result.events[0].event_id, result.events[1].event_id)
        self.assertEqual(len(result.events[0].fact_ids), 1)
        self.assertEqual(len(result.events[1].fact_ids), 1)

    def test_unknown_evidence_id_is_rejected(self) -> None:
        raw = article("기사 본문입니다. " * 80)

        def make_drafts(request):
            return (FactDraft("bad", "주체", "행동", ("ev:another-article:0001",)),)

        with self.assertRaisesRegex(ValueError, "outside extraction request"):
            SemanticPipeline().extract_article(
                raw,
                topic_id="ai_tech",
                extractor=FakeExtractor(make_drafts),
            )

    def test_duplicate_draft_ids_are_rejected(self) -> None:
        raw = article("기사 본문입니다. " * 80)

        def make_drafts(request):
            evidence_id = request.evidence[0].evidence_id
            return (
                FactDraft("dup", "A", "발표", (evidence_id,)),
                FactDraft("dup", "B", "발표", (evidence_id,)),
            )

        with self.assertRaisesRegex(ValueError, "duplicate draft ids"):
            SemanticPipeline().extract_article(
                raw,
                topic_id="ai_tech",
                extractor=FakeExtractor(make_drafts),
            )

    def test_topic_must_come_from_acquisition_context(self) -> None:
        raw = article("기사 본문입니다. " * 80, topics=("economy",))
        extractor = FakeExtractor(lambda request: ())
        with self.assertRaisesRegex(ValueError, "topic_id must already be attached"):
            SemanticPipeline().extract_article(raw, topic_id="ai_tech", extractor=extractor)

    def test_empty_article_never_calls_extractor(self) -> None:
        raw = article("   \n  ")
        extractor = FakeExtractor(lambda request: (_ for _ in ()).throw(AssertionError("must not call")))
        result = SemanticPipeline().extract_article(raw, topic_id="ai_tech", extractor=extractor)
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.facts, ())
        self.assertEqual(result.events, ())
        self.assertEqual(extractor.requests, [])

    def test_extractor_must_return_tuple(self) -> None:
        raw = article("기사 본문입니다. " * 80)

        class BadExtractor:
            extractor_id = "bad"

            def extract(self, request):
                return []

        with self.assertRaisesRegex(TypeError, "must return tuple"):
            SemanticPipeline().extract_article(raw, topic_id="ai_tech", extractor=BadExtractor())


if __name__ == "__main__":
    unittest.main()
