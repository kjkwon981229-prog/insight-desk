from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.kiwi_extractor import KiwiDeterministicFactExtractor
from insight_desk.semantic.pipeline import SemanticPipeline


HAS_KIWI = importlib.util.find_spec("kiwipiepy") is not None
NOW = datetime(2026, 9, 2, 3, 53, tzinfo=timezone.utc)


def _article(body: str, *, suffix: str) -> RawArticle:
    return RawArticle(
        article_id=f"structural-prefix-{suffix}",
        provenance=SourceProvenance(
            source_id=f"fixture:{suffix}",
            source_name="fixture",
            url=f"https://example.invalid/{suffix}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="메이크업포에버, NMIXX 글로벌 앰버서더 발탁",
        body=body,
        topic_ids=("kpop",),
    )


def _extract(body: str, *, suffix: str):
    return SemanticPipeline().extract_article(
        _article(body, suffix=suffix),
        topic_id="kpop",
        extractor=KiwiDeterministicFactExtractor(),
    )


@unittest.skipUnless(HAS_KIWI, "semantic-local optional dependency not installed")
class KiwiStructuralPrefixTests(unittest.TestCase):
    def test_detached_non_predicative_byline_prefix_is_not_part_of_exact_fact_span(self) -> None:
        body = (
            "컨슈머타임스=안솔지 기자 | "
            "메이크업포에버가 걸그룹 NMIXX(엔믹스)를 브랜드 최초의 K-POP 아이돌 "
            "글로벌 앰버서더로 발탁했다."
        )
        result = _extract(body, suffix="byline")

        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        exact = next(span.text for span in result.evidence if span.evidence_id in fact.evidence_ids)
        self.assertEqual(
            exact,
            "메이크업포에버가 걸그룹 NMIXX(엔믹스)를 브랜드 최초의 K-POP 아이돌 "
            "글로벌 앰버서더로 발탁했다.",
        )
        self.assertNotIn("컨슈머타임스", exact)
        self.assertNotIn("안솔지 기자", exact)

    def test_predicative_context_before_pipe_is_not_trimmed_as_metadata(self) -> None:
        body = "업계에 따르면 | 네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
        article = RawArticle(
            article_id="structural-prefix-context",
            provenance=SourceProvenance(
                source_id="fixture:context",
                source_name="fixture",
                url="https://example.invalid/context",
                retrieved_via="fixture",
                fetched_at=NOW,
                published_at=NOW,
            ),
            title="AI 공장 수주",
            body=body,
            topic_ids=("ai_tech",),
        )
        result = SemanticPipeline().extract_article(
            article,
            topic_id="ai_tech",
            extractor=KiwiDeterministicFactExtractor(),
        )

        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        exact = next(span.text for span in result.evidence if span.evidence_id in fact.evidence_ids)
        self.assertEqual(exact, body)


if __name__ == "__main__":
    unittest.main()
