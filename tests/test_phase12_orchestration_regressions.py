from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
from pathlib import Path
import unittest

from insight_desk.acquisition import ArticleCandidate
from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.generation import GeneratedDraft, GenerationContractError, GenerationRequest
from insight_desk.generation_pipeline import (
    ExtractiveFallbackGenerator,
    GenerationAttemptStatus,
    generate_with_recovery,
)
from insight_desk.semantic import EvidenceSegmenter, FactDraft, SemanticPipeline
import scripts.phase11_daily_production as production
import scripts.validate_feed_artifact as feed_validator


NOW = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
TARGET_SENTENCE = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
NEIGHBOR_SENTENCE = "정부는 별도 세제 지원책을 검토하고 있다."
TAIL_SENTENCE = "회사는 세부 계약 조건을 추후 공개할 예정이다."


def raw_article(body: str, *, article_id: str = "article:phase12") -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id="web:example.com",
            source_name="example.com",
            url=f"https://example.com/{article_id}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="AI 공장 수주",
        body=body,
        topic_ids=("ai_tech",),
        query="AI 공장",
    )


class FakeExtractor:
    extractor_id = "phase12-exact-sentence-fixture"

    def __init__(self, drafts_factory) -> None:
        self._drafts_factory = drafts_factory

    def extract(self, request):
        return self._drafts_factory(request)


def exact_sentence_result():
    body = f"{NEIGHBOR_SENTENCE} {TARGET_SENTENCE} {TAIL_SENTENCE}"
    raw = raw_article(body)
    target_start = body.index(TARGET_SENTENCE)
    target_end = target_start + len(TARGET_SENTENCE)

    def drafts(request):
        parent = next(
            span
            for span in request.evidence
            if span.start <= target_start and span.end >= target_end
        )
        return (
            FactDraft(
                draft_id="target",
                subject="네오팩토리",
                action="AI 공장 구축 사업을 15억달러에 수주했다",
                object="AI 공장 구축 사업",
                evidence_ids=(parent.evidence_id,),
                source_start=target_start,
                source_end=target_end,
            ),
        )

    result = SemanticPipeline(segmenter=EvidenceSegmenter(max_chars=1800)).extract_article(
        raw,
        topic_id="ai_tech",
        extractor=FakeExtractor(drafts),
    )
    return raw, result, target_start, target_end


def generation_request(text: str = TARGET_SENTENCE) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:phase12",
        article_id="article:phase12-generation",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:phase12",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase12",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


def html_for(*stories: tuple[str, str, str, str]) -> str:
    rows = []
    for index, (event_id, topic, headline, summary) in enumerate(stories, start=1):
        rows.append(
            f'<article id="story-{index}" class="story-row" data-event-id="{event_id}">'
            '<div class="story-main">'
            f'<div class="story-meta"><span class="story-topic">{topic}</span></div>'
            f'<h3>{headline}</h3>'
            f'<p class="story-summary">{summary}</p>'
            '</div></article>'
        )
    return '<!doctype html><html><body>' + ''.join(rows) + '</body></html>'


class FactEvidenceGranularityRegressions(unittest.TestCase):
    def test_fact_cites_exact_source_sentence_not_parent_window(self) -> None:
        raw, result, target_start, target_end = exact_sentence_result()
        self.assertEqual(len(result.facts), 1)
        fact = result.facts[0]
        cited = [span for span in result.evidence if span.evidence_id in fact.evidence_ids]
        self.assertEqual(len(cited), 1)
        self.assertEqual(cited[0].text, TARGET_SENTENCE)
        self.assertEqual((cited[0].start, cited[0].end), (target_start, target_end))
        cited[0].validate_against(raw)

    def test_neighbor_sentence_cannot_enter_extract_fallback(self) -> None:
        _, result, _, _ = exact_sentence_result()
        fact = result.facts[0]
        event = result.events[0]
        request = GenerationRequest(
            event=event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span for span in result.evidence},
        )
        draft = ExtractiveFallbackGenerator().generate(request)
        self.assertIn("네오팩토리", draft.combined_text)
        self.assertNotIn("세제 지원책", draft.combined_text)
        self.assertNotIn("세부 계약 조건", draft.combined_text)

    def test_out_of_parent_sentence_provenance_fails_closed(self) -> None:
        body = TARGET_SENTENCE
        raw = raw_article(body)

        def drafts(request):
            parent = request.evidence[0]
            return (
                FactDraft(
                    draft_id="bad-range",
                    subject="네오팩토리",
                    action="수주했다",
                    evidence_ids=(parent.evidence_id,),
                    source_start=parent.end + 1,
                    source_end=parent.end + 5,
                ),
            )

        with self.assertRaisesRegex(ValueError, "source.*outside|outside.*source|evidence.*range"):
            SemanticPipeline().extract_article(
                raw,
                topic_id="ai_tech",
                extractor=FakeExtractor(drafts),
            )


class SourceIdentityRegressions(unittest.TestCase):
    @staticmethod
    def candidate(candidate_id: str, url: str) -> ArticleCandidate:
        return ArticleCandidate(
            candidate_id=candidate_id,
            url=url,
            search_title="AI 공장 수주",
            source_name="example.com",
            published_at=NOW,
            topic_ids=("ai_tech",),
            query="AI 공장",
        )

    def test_original_and_alternate_share_source_group(self) -> None:
        self.assertTrue(hasattr(production, "_source_group_key"))
        original = self.candidate("article-deadbeef", "https://publisher.example/a")
        alternate = self.candidate("article-deadbeef-alt", "https://news.naver.com/a")
        self.assertEqual(
            production._source_group_key(original),
            production._source_group_key(alternate),
        )

    def test_normalized_body_fingerprint_deduplicates_url_variants_only(self) -> None:
        self.assertTrue(hasattr(production, "_content_fingerprint"))
        left = "첫 문장입니다.\n\n둘째 문장입니다."
        spacing_variant = "  첫 문장입니다.   둘째   문장입니다.  "
        different = "완전히 다른 기사 본문입니다."
        self.assertEqual(
            production._content_fingerprint(left),
            production._content_fingerprint(spacing_variant),
        )
        self.assertNotEqual(
            production._content_fingerprint(left),
            production._content_fingerprint(different),
        )

    def test_successful_article_publish_terminates_its_event_loop(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        event_loop = source[source.index("for event in semantic_result.events:") :]
        publish_at = event_loop.index("published.append")
        briefing_at = event_loop.index("briefing_id =", publish_at)
        try:
            break_at = event_loop.index("\n                    break", publish_at, briefing_at)
        except ValueError as exc:
            self.fail("published article must break out of its remaining semantic-event loop")
        self.assertLess(publish_at, break_at)


class GenerationHardContractRegressions(unittest.TestCase):
    def test_oversized_headline_is_rejected_at_generation_boundary(self) -> None:
        with self.assertRaises(GenerationContractError):
            GeneratedDraft(
                event_id="event:oversized-headline",
                headline="가" * 121,
                summary="정상 요약",
                evidence_ids=("ev:1",),
            )

    def test_oversized_summary_is_rejected_at_generation_boundary(self) -> None:
        with self.assertRaises(GenerationContractError):
            GeneratedDraft(
                event_id="event:oversized-summary",
                headline="정상 제목",
                summary="나" * 421,
                evidence_ids=("ev:1",),
            )

    def test_output_contract_rejection_is_not_provider_error(self) -> None:
        self.assertTrue(hasattr(GenerationAttemptStatus, "OUTPUT_CONTRACT_REJECTED"))

        class ContractRejectingGenerator:
            def generate(self, request):
                raise GenerationContractError("synthetic output contract violation")

        result = generate_with_recovery(
            generation_request(),
            primary=ContractRejectingGenerator(),
        )
        self.assertEqual(
            [attempt.status for attempt in result.attempts[:2]],
            [
                GenerationAttemptStatus.OUTPUT_CONTRACT_REJECTED,
                GenerationAttemptStatus.OUTPUT_CONTRACT_REJECTED,
            ],
        )


class ArtifactProvenanceRegressions(unittest.TestCase):
    def test_validator_report_binds_to_exact_html_sha256(self) -> None:
        page = html_for(
            ("event:a", "AI·테크", "AI 투자 확대", "A사가 AI 투자를 확대한다고 밝혔다."),
        )
        report = feed_validator.validate_html(page)
        self.assertEqual(
            report.get("html_sha256"),
            hashlib.sha256(page.encode("utf-8")).hexdigest(),
        )

    def test_validator_rejects_source_group_duplicate_from_audit(self) -> None:
        self.assertIn("source_audit", inspect.signature(feed_validator.validate_html).parameters)
        page = html_for(
            ("event:a", "AI·테크", "첫 번째 사실", "첫 번째 사실의 요약이다."),
            ("event:b", "AI·테크", "두 번째 사실", "두 번째 사실의 요약이다."),
        )
        audit = {
            "rendered_sources": [
                {"event_id": "event:a", "source_group_key": "source:1", "content_sha256": "a" * 64},
                {"event_id": "event:b", "source_group_key": "source:1", "content_sha256": "b" * 64},
            ]
        }
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_DUPLICATE_SOURCE"):
            feed_validator.validate_html(page, source_audit=audit)

    def test_validator_rejects_content_fingerprint_duplicate_from_audit(self) -> None:
        self.assertIn("source_audit", inspect.signature(feed_validator.validate_html).parameters)
        page = html_for(
            ("event:a", "AI·테크", "첫 번째 사실", "첫 번째 사실의 요약이다."),
            ("event:b", "AI·테크", "두 번째 사실", "두 번째 사실의 요약이다."),
        )
        audit = {
            "rendered_sources": [
                {"event_id": "event:a", "source_group_key": "source:1", "content_sha256": "a" * 64},
                {"event_id": "event:b", "source_group_key": "source:2", "content_sha256": "a" * 64},
            ]
        }
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_DUPLICATE_SOURCE_CONTENT"):
            feed_validator.validate_html(page, source_audit=audit)

    def test_validator_requires_html_and_audit_event_identity_match(self) -> None:
        self.assertIn("source_audit", inspect.signature(feed_validator.validate_html).parameters)
        page = html_for(
            ("event:a", "AI·테크", "AI 투자 확대", "A사가 AI 투자를 확대한다고 밝혔다."),
        )
        audit = {
            "rendered_sources": [
                {"event_id": "event:other", "source_group_key": "source:1", "content_sha256": "a" * 64},
            ]
        }
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_SOURCE_AUDIT_EVENT_MISMATCH"):
            feed_validator.validate_html(page, source_audit=audit)


class ProductionControlPlaneRegressions(unittest.TestCase):
    def test_phase12_second_live_production_workflow_is_removed(self) -> None:
        self.assertFalse(Path(".github/workflows/phase12-feed-artifact-audit.yml").exists())

    def test_production_pr_trigger_covers_entire_runtime_package(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertIn('      - "insight_desk/**"', workflow)

    def test_canonical_pr_artifact_contains_site_and_all_acceptance_reports(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        artifact_section = workflow[workflow.index("name: production-site-preflight") :]
        for required in (
            "build/site",
            "build/run-state.json",
            "build/production-audit.json",
            "build/feed-quality.json",
        ):
            self.assertIn(required, artifact_section)
        self.assertIn("--audit build/production-audit.json", workflow)

    def test_daily_production_has_no_unused_groq120b_call(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertNotIn("GROQ_120B", source)
        self.assertNotIn("temporal_auxiliary=temporal_auxiliary", source)

    def test_production_audit_exposes_safe_generation_attempt_aggregates(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn('"generation_stats"', source)
        self.assertIn('"rendered_sources"', source)


if __name__ == "__main__":
    unittest.main()
