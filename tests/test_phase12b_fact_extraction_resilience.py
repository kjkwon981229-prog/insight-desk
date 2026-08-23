from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.evidence import EvidenceSegmenter
from insight_desk.semantic.facts import FactDraft, FactExtractionRequest
from insight_desk.semantic.fallback_extractors import (
    LazyFactExtractor,
    PecabDeterministicFactExtractor,
    SequentialFactExtractor,
    SurfaceDeterministicFactExtractor,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def request(body: str) -> FactExtractionRequest:
    article = RawArticle(
        article_id="phase12b-fact",
        provenance=SourceProvenance(
            source_id="fixture:phase12b",
            source_name="fixture",
            url="https://example.invalid/phase12b-fact",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="테스트",
        body=body,
        topic_ids=("economy",),
    )
    evidence = tuple(
        span for span in EvidenceSegmenter().segment(article)
        if span.field.value == "body"
    )
    return FactExtractionRequest(article=article, topic_id="economy", evidence=evidence)


class GoodAnalyzer:
    def pos(self, text: str):
        del text
        return (("정부", "NNG"), ("는", "JX"), ("밝혔다", "VV"))


class BadAnalyzer:
    def pos(self, text: str):
        del text
        return (("정부", "NNG"),)


@dataclass
class Route:
    extractor_id: str
    result: tuple[FactDraft, ...]
    calls: int = 0

    def extract(self, item: FactExtractionRequest) -> tuple[FactDraft, ...]:
        del item
        self.calls += 1
        return self.result


def fake_draft(prefix: str = "route") -> FactDraft:
    return FactDraft(
        draft_id=f"{prefix}:1",
        subject="정부",
        action="새 제도를 시행한다고 밝혔다",
        evidence_ids=("ev:1",),
    )


class Phase12BFactExtractionResilienceTests(unittest.TestCase):
    def test_surface_fallback_preserves_exact_sentence_offsets(self) -> None:
        body = "머리말입니다.\n정부는 9월 3일부터 새 제도를 시행한다고 밝혔다.\n꼬리말입니다."
        item = request(body)
        drafts = SurfaceDeterministicFactExtractor().extract(item)
        target = next(draft for draft in drafts if draft.subject == "정부")
        self.assertEqual(target.action, "9월 3일부터 새 제도를 시행한다고 밝혔다")
        self.assertIsNotNone(target.source_start)
        self.assertIsNotNone(target.source_end)
        exact = body[target.source_start : target.source_end]
        self.assertEqual(exact, "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다.")
        self.assertIn(target.subject, exact)
        self.assertIn(target.action, exact)

    def test_surface_fallback_refuses_nested_subject_attachment(self) -> None:
        body = "정부는 한국은행이 금리를 올렸다고 밝혔다."
        self.assertEqual(SurfaceDeterministicFactExtractor().extract(request(body)), ())

    def test_surface_fallback_refuses_non_declarative_fragment(self) -> None:
        body = "원·달러 환율 1386.5원"
        self.assertEqual(SurfaceDeterministicFactExtractor().extract(request(body)), ())

    def test_pecab_route_requires_case_and_predicate_tags(self) -> None:
        body = "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다."
        item = request(body)
        accepted = PecabDeterministicFactExtractor(GoodAnalyzer()).extract(item)
        rejected = PecabDeterministicFactExtractor(BadAnalyzer()).extract(item)
        self.assertEqual(len(accepted), 1)
        self.assertTrue(accepted[0].draft_id.startswith("pecab:"))
        self.assertEqual(rejected, ())

    def test_sequential_extractor_stops_at_first_nonempty_route(self) -> None:
        first = Route("first", ())
        second = Route("second", (fake_draft("second"),))
        third = Route("third", (fake_draft("third"),))
        extractor = SequentialFactExtractor((first, second, third))

        result = extractor.extract(request("정부는 새 제도를 시행한다고 밝혔다."))

        self.assertEqual(result[0].draft_id, "second:1")
        self.assertEqual((first.calls, second.calls, third.calls), (1, 1, 0))
        self.assertEqual(extractor.extractor_id, "kiwi-deterministic-v1")

    def test_lazy_route_treats_dependency_unavailability_as_empty(self) -> None:
        def unavailable():
            raise RuntimeError("missing local dependency")

        lazy = LazyFactExtractor("missing-route", unavailable)
        self.assertEqual(lazy.extract(request("정부는 새 제도를 시행한다고 밝혔다.")), ())

    def test_lazy_route_does_not_hide_programming_error(self) -> None:
        class Broken:
            extractor_id = "broken"

            def extract(self, item):
                del item
                raise AssertionError("programming bug")

        lazy = LazyFactExtractor("broken", Broken)
        with self.assertRaises(AssertionError):
            lazy.extract(request("정부는 새 제도를 시행한다고 밝혔다."))


if __name__ == "__main__":
    unittest.main()
