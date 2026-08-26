from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.production_runtime_v2 import production_v2_runtime
from insight_desk.semantic import EvidenceSegmenter, FactDraft
import scripts.phase11_daily_production as production


PUBLISHED_AT = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
OLD_CONTEXT = "제조사는 6월 16일 기존 생산시설 착공식을 열었다."
CURRENT_EVENT = "제조사는 8월 27일 신규 AI 광통신 투자 계획을 발표했다."


class OrderedExtractor:
    extractor_id = "phase8-primary-event-fixture"

    def __init__(self, drafts: tuple[tuple[str, str, str, str], ...]) -> None:
        self._drafts = drafts

    def extract(self, request):
        resolved = []
        for draft_id, sentence, subject, event_date in self._drafts:
            start = request.article.body.index(sentence)
            end = start + len(sentence)
            parent = next(
                span
                for span in request.evidence
                if span.start <= start and span.end >= end
            )
            resolved.append(
                FactDraft(
                    draft_id=draft_id,
                    subject=subject,
                    action=sentence.removeprefix(subject).strip(),
                    evidence_ids=(parent.evidence_id,),
                    event_date=event_date,
                    source_start=start,
                    source_end=end,
                )
            )
        return tuple(resolved)


def article(article_id: str, body: str) -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id=f"web:{article_id}",
            source_name="example.com",
            url=f"https://example.com/{article_id}",
            retrieved_via="fixture",
            fetched_at=PUBLISHED_AT,
            published_at=PUBLISHED_AT,
        ),
        title="제조사, 신규 AI 광통신 투자 계획 발표",
        body=body,
        topic_ids=("ai_tech",),
        query="AI 광통신",
    )


def extract(raw: RawArticle, drafts: tuple[tuple[str, str, str, str], ...]):
    with production_v2_runtime(production._core):
        semantic = production._core.SemanticPipeline(
            segmenter=EvidenceSegmenter(max_chars=1800)
        )
        return semantic.extract_article(
            raw,
            topic_id="ai_tech",
            extractor=OrderedExtractor(drafts),
        )


class Live464PrimaryEventUnderstandingRegressions(unittest.TestCase):
    def test_explicit_old_context_does_not_outrank_publication_day_event(self) -> None:
        raw = article("mixed-current-context", f"{OLD_CONTEXT} {CURRENT_EVENT}")
        result = extract(
            raw,
            (
                ("old-context", OLD_CONTEXT, "제조사", "2026-06-16"),
                ("current", CURRENT_EVENT, "제조사", "2026-08-27"),
            ),
        )

        self.assertEqual(len(result.events), 1)
        selected = result.events[0]
        selected_fact = next(fact for fact in result.facts if fact.fact_id in selected.fact_ids)
        self.assertEqual(selected_fact.event_date, "2026-08-27")
        self.assertIn("신규 AI 광통신 투자 계획", selected_fact.action)

    def test_single_historical_event_is_preserved(self) -> None:
        raw = article("single-historical", OLD_CONTEXT)
        result = extract(
            raw,
            (("old-only", OLD_CONTEXT, "제조사", "2026-06-16"),),
        )
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.facts[0].event_date, "2026-06-16")

    def test_all_historical_multi_event_article_is_not_collapsed_by_recency_alone(self) -> None:
        older = "제조사는 5월 2일 연구개발센터를 개소했다."
        raw = article("historical-feature", f"{older} {OLD_CONTEXT}")
        result = extract(
            raw,
            (
                ("older", older, "제조사", "2026-05-02"),
                ("old-context", OLD_CONTEXT, "제조사", "2026-06-16"),
            ),
        )
        self.assertEqual(len(result.events), 2)

    def test_undated_multi_event_article_is_preserved_when_primary_is_unresolved(self) -> None:
        first = "제조사는 광통신 생산능력을 확대했다."
        second = "제조사는 신규 고객사와 공급 협의를 진행하고 있다."
        raw = article("ambiguous-undated", f"{first} {second}")
        result = extract(
            raw,
            (
                ("first", first, "제조사", ""),
                ("second", second, "제조사", ""),
            ),
        )
        self.assertEqual(len(result.events), 2)


if __name__ == "__main__":
    unittest.main()
