from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    EventFact,
    RawArticle,
    SourceProvenance,
)
import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
import insight_desk.production_orchestrator_compat_v2 as orchestrator_compat_v2
import insight_desk.production_orchestrator_v2 as orchestrator_v2
from insight_desk.production_orchestrator_v2 import (
    CanonicalIdentityEngine,
    ProductionV2Registry,
    source_document_from_article,
)
from insight_desk.production_runtime_v2 import production_v2_runtime
import insight_desk.production_phase7_v2 as phase7_scope
import scripts.phase11_daily_production as production
import scripts.validate_feed_artifact as feed_validator


NOW = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)


def article(article_id: str, body: str) -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id=f"web:{article_id}",
            source_name="example.com",
            url=f"https://example.com/{article_id}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="한국은행 금융통화위원회",
        body=body,
        topic_ids=("economy",),
        query="한국은행 기준금리",
    )


def event_fact(
    *,
    article_id: str,
    event_id: str,
    fact_id: str,
    evidence_id: str,
) -> tuple[CandidateEvent, EventFact]:
    fact = EventFact(
        fact_id=fact_id,
        subject="한국은행 금융통화위원회",
        action="기준금리를 결정한다",
        object="기준금리",
        evidence_ids=(evidence_id,),
        event_date="2026-08-27",
        participants=("한국은행", "금융통화위원회"),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(article_id,),
    )
    return event, fact


def v2_html(*, source_url: str = "https://example.com/20200101/source") -> str:
    return (
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:v2">'
        '<div class="story-main">'
        '<div class="story-meta"><span class="story-topic">경제·투자</span></div>'
        '<h3>이번 결정</h3>'
        '<p class="story-summary">이는 시장에 영향을 준다.</p>'
        f'<a class="story-source" href="{source_url}">원문 보기</a>'
        '</div></article></body></html>'
    )


def v2_audit(*, validated: bool = True, source_url: str = "https://example.com/20200101/source") -> dict[str, object]:
    return {
        "publication_contract_version": 2,
        "canonical_contract": {"validated": validated},
        "runtime_authority": {
            "story_admission_semantic_gate": False,
            "visible_identity_semantic_gate": False,
        },
        "rendered_sources": [
            {
                "event_id": "event:v2",
                "source_group_key": "source-group:v2",
                "content_sha256": "a" * 64,
                "source_url": source_url,
            }
        ],
    }


class ProductionAuthorityWiringTests(unittest.TestCase):
    def test_entrypoint_has_no_executable_story_admission_or_feed_quality_import(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn("production_v2_runtime", source)
        self.assertNotIn("from insight_desk.story_admission", source)
        self.assertNotIn("from insight_desk.feed_quality", source)

    def test_importing_production_keeps_legacy_helpers_unmodified(self) -> None:
        self.assertIs(
            generation_module.validate_story_admission,
            phase7_scope._ORIGINAL_GENERATION_STORY_ADMISSION,
        )
        self.assertIs(
            generation_pipeline_module.validate_story_admission,
            phase7_scope._ORIGINAL_PIPELINE_STORY_ADMISSION,
        )
        self.assertFalse(
            getattr(production._core.produce_phase7_entry_candidate, "_insight_desk_v2_scoped", False)
        )
        self.assertFalse(hasattr(production._core, "_INSIGHT_DESK_V2_REGISTRY"))

    def test_v2_facade_does_not_export_direct_candidate_to_canonical_builder(self) -> None:
        self.assertFalse(hasattr(orchestrator_v2, "canonical_event_from_candidate"))
        self.assertFalse(hasattr(orchestrator_compat_v2, "canonical_event_from_candidate"))
        self.assertFalse(hasattr(ProductionV2Registry(), "register_article_result"))

    def test_compatibility_reinstall_cannot_replace_runtime_semantic_authority(self) -> None:
        with production_v2_runtime(production._core) as registry:
            active_pipeline = production._core.SemanticPipeline
            returned = orchestrator_compat_v2.install_production_orchestration(
                production._core
            )
            self.assertIs(returned, registry)
            self.assertIs(production._core.SemanticPipeline, active_pipeline)
            self.assertEqual(
                active_pipeline.__module__,
                "insight_desk.production_event_understanding_lifecycle_v2",
            )

    def test_v2_authority_exists_only_inside_actual_runtime_scope(self) -> None:
        original_relevance = production._core.event_topic_relevant
        original_phase7 = production._core.produce_phase7_entry_candidate
        original_semantic = production._core.SemanticPipeline
        with production_v2_runtime(production._core) as registry:
            self.assertIsInstance(registry, ProductionV2Registry)
            self.assertIsNot(production._core.event_topic_relevant, original_relevance)
            self.assertTrue(
                getattr(
                    production._core.produce_phase7_entry_candidate,
                    "_insight_desk_v2_scoped",
                    False,
                )
            )
            self.assertIs(production._core._INSIGHT_DESK_V2_REGISTRY, registry)
            self.assertEqual(
                production._core.SemanticPipeline.__module__,
                "insight_desk.production_event_understanding_lifecycle_v2",
            )
            self.assertEqual(
                production._core.SemanticPipeline.__name__,
                "EventUnderstandingSemanticPipeline",
            )
        self.assertIs(production._core.event_topic_relevant, original_relevance)
        self.assertIs(production._core.produce_phase7_entry_candidate, original_phase7)
        self.assertIs(production._core.SemanticPipeline, original_semantic)
        self.assertFalse(hasattr(production._core, "_INSIGHT_DESK_V2_REGISTRY"))
        self.assertIs(
            generation_module.validate_story_admission,
            phase7_scope._ORIGINAL_GENERATION_STORY_ADMISSION,
        )

    def test_source_document_is_bound_to_exact_article_body_bytes(self) -> None:
        raw = article("article:source", "첫 문장입니다.\n둘째 문장입니다.")
        source = source_document_from_article(raw)
        self.assertEqual(source.candidate_ids, (raw.article_id,))
        self.assertEqual(source.body, raw.body)
        self.assertEqual(
            source.content_sha256,
            hashlib.sha256(raw.body.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(source.url, raw.provenance.url)
        self.assertEqual(source.publication_time, raw.provenance.published_at)


class CanonicalIdentityOwnerTests(unittest.TestCase):
    def test_scheduled_bok_children_get_one_parent_inside_identity_owner(self) -> None:
        left_article = article(
            "article:bok-left",
            "한국은행 금융통화위원회는 27일 기준금리를 결정한다. 수정 경제전망도 공개한다.",
        )
        right_article = article(
            "article:bok-right",
            "한은 금통위는 27일 기준금리를 결정한다. 회의 뒤 전망 자료를 발표한다.",
        )
        left_event, left_fact = event_fact(
            article_id=left_article.article_id,
            event_id="event:bok-left",
            fact_id="fact:bok-left",
            evidence_id="evidence:bok-left",
        )
        right_event, right_fact = event_fact(
            article_id=right_article.article_id,
            event_id="event:bok-right",
            fact_id="fact:bok-right",
            evidence_id="evidence:bok-right",
        )

        registry = ProductionV2Registry(
            events_by_id={
                left_event.event_id: CanonicalEvent(
                    event_id=left_event.event_id,
                    topic="economy",
                    actor=left_fact.subject,
                    action=left_fact.action,
                    object=left_fact.object,
                    event_type="news_event",
                    source_ids=("source:bok-left",),
                    event_time=left_fact.event_date,
                    participants=left_fact.participants,
                ),
                right_event.event_id: CanonicalEvent(
                    event_id=right_event.event_id,
                    topic="economy",
                    actor=right_fact.subject,
                    action=right_fact.action,
                    object=right_fact.object,
                    event_type="news_event",
                    source_ids=("source:bok-right",),
                    event_time=right_fact.event_date,
                    participants=right_fact.participants,
                ),
            }
        )

        owner = CanonicalIdentityEngine(registry)
        facts = {
            left_fact.fact_id: left_fact,
            right_fact.fact_id: right_fact,
        }
        precheck = owner.precheck(left_event, right_event, facts)
        self.assertFalse(precheck.deterministic_block)

        class UnusedVerifier:
            verifier_id = "unused"
            model_id = "unused"

            def verify(self, **_kwargs):
                raise AssertionError("BOK parent-child identity should resolve before verifier calls")

        judgment = owner.judge(
            left_article.body,
            right_article.body,
            primary=UnusedVerifier(),
            secondary=UnusedVerifier(),
        )
        self.assertTrue(judgment.same_event)
        self.assertEqual(judgment.primary_checks, 0)
        self.assertEqual(judgment.secondary_checks, 0)
        left = registry.canonical_event(left_event.event_id)
        right = registry.canonical_event(right_event.event_id)
        self.assertIsNotNone(left.parent_event_id)
        self.assertEqual(left.parent_event_id, right.parent_event_id)
        self.assertIn(left.parent_event_id, registry.parent_events_by_id)


class V2ArtifactContractTests(unittest.TestCase):
    def test_v2_artifact_validator_does_not_rejudge_visible_news_semantics(self) -> None:
        report = feed_validator.validate_html(v2_html(), source_audit=v2_audit())
        self.assertEqual(report["publication_contract_version"], 2)
        self.assertFalse(report["semantic_revalidation"])
        self.assertEqual(report["context_dependent_headlines"], 0)
        self.assertEqual(report["context_dependent_summaries"], 0)
        self.assertEqual(report["stale_source_urls"], 0)

    def test_v2_artifact_requires_a_validated_canonical_bundle(self) -> None:
        with self.assertRaisesRegex(ValueError, "CANONICAL_CONTRACT_UNVALIDATED"):
            feed_validator.validate_html(
                v2_html(),
                source_audit=v2_audit(validated=False),
            )

    def test_legacy_artifact_without_v2_audit_keeps_historical_semantic_regressions(self) -> None:
        with self.assertRaises(ValueError):
            feed_validator.validate_html(v2_html())


if __name__ == "__main__":
    unittest.main()
