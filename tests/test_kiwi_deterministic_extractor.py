from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.kiwi_extractor import KiwiDeterministicFactExtractor
from insight_desk.semantic.pipeline import SemanticPipeline


HAS_KIWI = importlib.util.find_spec("kiwipiepy") is not None
NOW = datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc)
_EXTRACTOR: KiwiDeterministicFactExtractor | None = None
_PIPELINE = SemanticPipeline()


def raw_article(title: str, body: str, *, topic_id: str = "ai_tech", suffix: str = "x") -> RawArticle:
    return RawArticle(
        article_id=f"kiwi-canary-{suffix}",
        provenance=SourceProvenance(
            source_id="fixture:phase6",
            source_name="phase6-fixture",
            url=f"https://example.invalid/{suffix}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title=title,
        body=body,
        topic_ids=(topic_id,),
    )


def extractor() -> KiwiDeterministicFactExtractor:
    global _EXTRACTOR
    if _EXTRACTOR is None:
        _EXTRACTOR = KiwiDeterministicFactExtractor()
    return _EXTRACTOR


def extract(title: str, body: str, *, topic_id: str = "ai_tech", suffix: str = "x"):
    return _PIPELINE.extract_article(
        raw_article(title, body, topic_id=topic_id, suffix=suffix),
        topic_id=topic_id,
        extractor=extractor(),
    )


@unittest.skipUnless(HAS_KIWI, "semantic-local optional dependency not installed")
class KiwiDeterministicFactExtractorTests(unittest.TestCase):
    def test_all_locked_korean_run96_positive_leads_emit_evidence_bound_fact(self) -> None:
        data = json.loads(Path("benchmarks/run96_recall_precision.json").read_text(encoding="utf-8"))
        korean_cases = [
            item for item in data["positive_events"] if re.search(r"[가-힣]", item["lead"])
        ]
        self.assertEqual(len(korean_cases), 14)

        missing: list[str] = []
        for item in korean_cases:
            result = extract(
                item["title"],
                item["lead"],
                topic_id=item["topic_id"],
                suffix=item["id"],
            )
            if not result.facts:
                missing.append(item["id"])
                continue
            for fact in result.facts:
                cited = "\n".join(
                    span.text for span in result.evidence if span.evidence_id in fact.evidence_ids
                )
                self.assertIn(fact.subject, cited)
                self.assertIn(fact.action, cited)
                if fact.object is not None:
                    self.assertIn(fact.object, cited)
        self.assertEqual(missing, [])

    def test_context_only_nominals_emit_no_fact(self) -> None:
        cases = (
            "데이터 중심으로 기술 모으는 오라클의 AI 전략",
            "원·달러 환율 1417.53원",
            "한화 선발 화이트의 역투",
        )
        for index, text in enumerate(cases):
            result = extract(text, text, suffix=f"context-{index}")
            self.assertEqual(result.facts, (), text)

    def test_policy_rate_statement_prefers_explicit_topic_over_embedded_nominative(self) -> None:
        text = "한국은행 부총재는 특별한 충격이 없다면 기준금리를 추가 인상할 수 있다고 밝혔다."
        result = extract("기준금리 추가 인상 가능성", text, topic_id="economy", suffix="rate")
        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        self.assertEqual(fact.subject, "한국은행 부총재")
        self.assertEqual(fact.object, "기준금리")
        self.assertEqual(fact.action, "특별한 충격이 없다면 기준금리를 추가 인상할 수 있다고 밝혔다")

    def test_malformed_lineup_does_not_invent_missing_starters(self) -> None:
        text = "한화 이글스와 두산 베어스의 선발이 예고됐다."
        result = extract("선발 예고", text, topic_id="kbo_hanwha", suffix="lineup")
        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        self.assertEqual(fact.subject, "선발")
        self.assertEqual(fact.action, "예고됐다")
        self.assertNotIn("왕옌청", fact.subject + fact.action + (fact.object or ""))
        self.assertNotIn("곽빈", fact.subject + fact.action + (fact.object or ""))

    def test_amounts_and_market_direction_survive_inside_exact_fact_fields(self) -> None:
        order = extract(
            "AI 공장 수주",
            "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.",
            suffix="order",
        ).facts[0]
        self.assertIn("15억달러", order.action)
        self.assertEqual(order.object, "AI 공장 구축 사업")

        market = extract(
            "코스피 급등",
            "코스피가 소비자물가 둔화에 3.4% 급등해 마감했다.",
            topic_id="economy",
            suffix="market",
        ).facts[0]
        self.assertIn("3.4%", market.action)
        self.assertIn("급등", market.action)

    def test_unsupported_english_sentence_fails_closed_without_global_error(self) -> None:
        text = "BTS' Arirang remained No. 14 on the Billboard 200 for a 20th week."
        result = extract(text, text, topic_id="kpop", suffix="english")
        self.assertEqual(result.facts, ())
        self.assertEqual(result.events, ())


if __name__ == "__main__":
    unittest.main()
