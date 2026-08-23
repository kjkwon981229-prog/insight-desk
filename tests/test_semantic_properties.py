from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.kiwi_extractor import KiwiDeterministicFactExtractor
from insight_desk.semantic.pipeline import SemanticPipeline
from insight_desk.semantic.tooling import KiwiMorphologyHelper

HAS_PROPERTY_QA = importlib.util.find_spec("hypothesis") is not None and importlib.util.find_spec("kiwipiepy") is not None
NOW = datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc)

if HAS_PROPERTY_QA:
    from hypothesis import given, settings, strategies as st

    _KIWI = KiwiMorphologyHelper()
    _EXTRACTOR = KiwiDeterministicFactExtractor()
    _PIPELINE = SemanticPipeline()
    SUBJECTS = ("정부", "삼성전자", "네오팩토리", "한국은행", "한화")
    OBJECTS = ("규제안", "신규 사업", "AI 공장", "전속계약", "지원 계획")
    ACTIONS = ("발표했다", "지원했다", "확대했다", "중단했다", "공급했다")
    SENTENCES = (
        "정부가 규제안을 발표했다.",
        "삼성전자가 신규 사업을 확대했다.",
        "네오팩토리가 AI 공장을 공급했다.",
        "한화가 지원 계획을 발표했다.",
    )

    def _article(body: str) -> RawArticle:
        return RawArticle(
            article_id="property-source",
            provenance=SourceProvenance(
                source_id="fixture:property", source_name="property",
                url="https://example.invalid/property", retrieved_via="fixture",
                fetched_at=NOW, published_at=NOW,
            ),
            title="property source preservation", body=body, topic_ids=("ai_tech",),
        )

    def _has_final_consonant(text: str) -> bool:
        last = next((char for char in reversed(text) if not char.isspace()), "")
        return "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0

    def _particle(text: str, consonant: str, vowel: str) -> str:
        return consonant if _has_final_consonant(text) else vowel

    class SemanticPropertyTests(unittest.TestCase):
        @settings(max_examples=40, deadline=None)
        @given(st.lists(st.sampled_from(SENTENCES), min_size=1, max_size=5), st.sampled_from((" ", "\n", "\n\n", "  ")))
        def test_sentence_spans_roundtrip_exact_source(self, sentences: list[str], separator: str) -> None:
            text = separator.join(sentences)
            spans = _KIWI.split_sentences(text)
            self.assertTrue(spans)
            for span in spans:
                self.assertEqual(span.text, text[span.start:span.end])

        @settings(max_examples=40, deadline=None)
        @given(st.sampled_from(SUBJECTS), st.sampled_from(OBJECTS), st.sampled_from(ACTIONS))
        def test_emitted_fact_fields_never_escape_cited_source(self, subject: str, object_text: str, action: str) -> None:
            body = f"{subject}{_particle(subject, '이', '가')} {object_text}{_particle(object_text, '을', '를')} {action}."
            result = _PIPELINE.extract_article(_article(body), topic_id="ai_tech", extractor=_EXTRACTOR)
            self.assertEqual(len(result.facts), 1)
            fact = result.facts[0]
            cited = "\n".join(span.text for span in result.evidence if span.evidence_id in fact.evidence_ids)
            self.assertIn(fact.subject, cited)
            self.assertIn(fact.action, cited)
            if fact.object is not None:
                self.assertIn(fact.object, cited)
else:
    @unittest.skip("qa + semantic-local optional dependencies not installed")
    class SemanticPropertyTests(unittest.TestCase):
        def test_optional_property_qa_is_not_base_runtime_dependency(self) -> None:
            self.fail("skip marker")


if __name__ == "__main__":
    unittest.main()
