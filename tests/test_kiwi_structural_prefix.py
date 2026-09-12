from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.kiwi_extractor import KiwiDeterministicFactExtractor
from insight_desk.semantic.pipeline import SemanticPipeline
from insight_desk.semantic.tooling import KiwiMorphologyHelper


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
    def test_bracketed_and_unicode_separator_bylines_preserve_exact_event(self) -> None:
        proposition = "삼성생명이 인공지능 기반 상담 훈련 서비스를 도입한다."
        for prefix in (
            "[직썰 / 손성은 기자] ",
            "[STN뉴스] 류승우 기자┃",
            "(엑스포츠뉴스 김수아 기자) ",
            "[법률저널=안혜성 기자] ",
            "【브레이크뉴스 대구】진예솔 기자=",
            "[서울=뉴스핌] 양태훈 기자 = ",
        ):
            with self.subTest(prefix=prefix):
                result = _extract(prefix + proposition, suffix="structured-byline")
                self.assertEqual(len(result.facts), 1)
                fact = result.facts[0]
                exact = next(span.text for span in result.evidence if span.evidence_id in fact.evidence_ids)
                self.assertEqual(exact, proposition, repr((fact, KiwiMorphologyHelper().analyze(prefix + proposition))))
                self.assertEqual(fact.subject, "삼성생명")

    def test_closed_reporter_credit_does_not_discard_event_descriptors_before_subject(self) -> None:
        credit = "[법률저널=안혜성 기자] "
        proposition = (
            "중앙행정기관, 공공기관 등 공직 채용정보를 확인하고, 현직 공무원 상담부터 "
            "모의면접까지 직접 체험할 수 있는 공직박람회가 9일부터 대전, 전남광주에서 "
            "차례로 열린다."
        )

        result = _extract(credit + proposition, suffix="closed-credit-with-descriptors")

        fact = next(item for item in result.facts if item.subject == "공직박람회")
        exact = next(
            span.text for span in result.evidence if span.evidence_id in fact.evidence_ids
        )
        self.assertEqual(exact, proposition)

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
