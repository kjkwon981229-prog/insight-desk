from __future__ import annotations

import unittest
from datetime import datetime, timezone

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic import EvidenceSegmenter, FactDraft, SemanticPipeline


PUBLISHED_AT = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


class _ExactSentenceExtractor:
    extractor_id = "phase7-explicit-date-fixture"

    def extract(self, request):
        sentence = "두 구단은 7일 서울에서 경기를 치렀다."
        start = request.article.body.index(sentence)
        end = start + len(sentence)
        parent = next(span for span in request.evidence if span.start <= start and span.end >= end)
        return (
            FactDraft(
                draft_id="dated-event",
                subject="두 구단",
                action="7일 서울에서 경기를 치렀다",
                evidence_ids=(parent.evidence_id,),
                source_start=start,
                source_end=end,
            ),
        )


class CurrentSentenceEventDateTests(unittest.TestCase):
    def test_explicit_date_in_exact_fact_sentence_is_preserved_as_event_date(self) -> None:
        body = (
            "최근 경기 흐름을 정리한 기사다. "
            "두 구단은 7일 서울에서 경기를 치렀다. "
            "이후 일정과 선수 소식도 함께 전했다."
        )
        article = RawArticle(
            article_id="article-explicit-date",
            provenance=SourceProvenance(
                source_id="web:fixture",
                source_name="fixture",
                url="https://example.com/dated-event",
                retrieved_via="fixture",
                fetched_at=PUBLISHED_AT,
                published_at=PUBLISHED_AT,
            ),
            title="최근 경기 흐름과 선수 소식",
            body=body,
            topic_ids=("sports",),
            query="sports",
        )

        result = SemanticPipeline(segmenter=EvidenceSegmenter(max_chars=500)).extract_article(
            article,
            topic_id="sports",
            extractor=_ExactSentenceExtractor(),
        )

        self.assertEqual(len(result.facts), 1)
        self.assertEqual(result.facts[0].event_date, "2026-08-07")


if __name__ == "__main__":
    unittest.main()
