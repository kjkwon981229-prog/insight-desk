from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import EvidenceField, EvidenceSpan, RawArticle, SourceProvenance
from insight_desk.semantic.facts import FactExtractionRequest
from insight_desk.semantic.fallback_extractors import SurfaceDeterministicFactExtractor


NOW = datetime(2026, 8, 26, 18, 1, 16, tzinfo=timezone.utc)


def extract_one(source: str):
    article = RawArticle(
        article_id="article:phase5-subject-boundary",
        provenance=SourceProvenance(
            source_id="source:phase5-subject-boundary",
            source_name="recorded.test",
            url="https://example.test/article",
            retrieved_via="recorded-test",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="recorded replay",
        body=source,
        topic_ids=("economy",),
    )
    evidence = EvidenceSpan.from_article(
        evidence_id="evidence:phase5-subject-boundary",
        article=article,
        field=EvidenceField.BODY,
        start=0,
        end=len(source),
    )
    drafts = SurfaceDeterministicFactExtractor().extract(
        FactExtractionRequest(
            article=article,
            topic_id="economy",
            evidence=(evidence,),
        )
    )
    return drafts


class Phase5KoreanSubjectBoundaryTests(unittest.TestCase):
    def test_bank_name_internal_eun_is_not_misread_as_subject_particle(self) -> None:
        source = "한국은행은 27일 기준금리를 결정한다."
        drafts = extract_one(source)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].subject, "한국은행")
        self.assertEqual(drafts[0].action, "27일 기준금리를 결정한다")
        self.assertEqual(source[drafts[0].source_start : drafts[0].source_end], source)

    def test_long_bok_actor_keeps_full_subject_until_actual_particle_boundary(self) -> None:
        source = "한국은행 금융통화위원회는 27일 회의를 열어 기준금리를 결정한다."
        drafts = extract_one(source)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].subject, "한국은행 금융통화위원회")
        self.assertEqual(
            drafts[0].action,
            "27일 회의를 열어 기준금리를 결정한다",
        )

    def test_existing_non_conflicting_subject_remains_extractable(self) -> None:
        source = "SSG 랜더스는 26일 한화 이글스를 6-1로 제압했다."
        drafts = extract_one(source)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].subject, "SSG 랜더스")
        self.assertEqual(drafts[0].action, "26일 한화 이글스를 6-1로 제압했다")


if __name__ == "__main__":
    unittest.main()
