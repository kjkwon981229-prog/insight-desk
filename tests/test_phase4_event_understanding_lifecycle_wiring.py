from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest import mock

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.core.event_understanding_v2 import UnderstandingStatus
from insight_desk.production_event_understanding_lifecycle_v2 import (
    install_event_understanding_lifecycle,
)
import insight_desk.production_event_understanding_lifecycle_v2 as lifecycle_module
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_runtime_v2 import production_v2_runtime
from insight_desk.semantic.pipeline import SemanticArticleResult
import scripts.phase11_daily_production as production


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


def _article(article_id: str, body: str) -> RawArticle:
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
        title="한국은행 금융통화위원회 기준금리 결정",
        body=body,
        topic_ids=("economy",),
        query="한국은행 기준금리",
    )


def _semantic_result(
    raw: RawArticle,
    *,
    subject: str,
    action: str,
) -> tuple[SemanticArticleResult, CandidateEvent]:
    evidence = EvidenceSpan.from_article(
        evidence_id=f"evidence:{raw.article_id}",
        article=raw,
        field=EvidenceField.BODY,
        start=0,
        end=len(raw.body),
    )
    fact = EventFact(
        fact_id=f"fact:{raw.article_id}",
        subject=subject,
        action=action,
        evidence_ids=(evidence.evidence_id,),
        event_date="2026-08-30",
    )
    event = CandidateEvent(
        event_id=f"event:{raw.article_id}",
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(raw.article_id,),
    )
    return (
        SemanticArticleResult(
            article_id=raw.article_id,
            extractor_id="fixture",
            evidence=(evidence,),
            facts=(fact,),
            events=(event,),
        ),
        event,
    )


class _RecordingAuthority:
    def __init__(self, registry: ProductionV2Registry) -> None:
        self.registry = registry
        self.calls: list[str] = []

    def enrich(self, event, source):
        # Authority must only see an already-resolved CanonicalEvent bound to its SourceDocument.
        self.registry.canonical_event(event.event_id)
        self.assert_source(event.event_id, source.source_id)
        self.calls.append(event.event_id)
        return ()

    def assert_source(self, event_id: str, source_id: str) -> None:
        event = self.registry.canonical_event(event_id)
        if event.source_ids != (source_id,):
            raise AssertionError("authority observed an event before source binding")


class EventUnderstandingLifecycleTests(unittest.TestCase):
    def test_resolved_primary_crosses_canonical_boundary_before_authority(self) -> None:
        raw = _article(
            "resolved",
            "한국은행 금융통화위원회는 기준금리를 결정한다.",
        )
        result, event = _semantic_result(
            raw,
            subject="한국은행 금융통화위원회",
            action="기준금리를 결정한다",
        )
        registry = ProductionV2Registry()
        authority = _RecordingAuthority(registry)
        core = SimpleNamespace(
            SemanticPipeline=object,
            event_understanding_decision=object(),
            _INSIGHT_DESK_V2_AUTHORITATIVE_OWNER=authority,
        )

        class FakeLegacySemanticPipeline:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def extract_article(self, _article, *, topic_id: str, extractor):
                del topic_id, extractor
                return result

        with (
            mock.patch.object(lifecycle_module, "LegacySemanticPipeline", FakeLegacySemanticPipeline),
            mock.patch.object(lifecycle_module, "_optional_morphology", return_value=None),
        ):
            install_event_understanding_lifecycle(core, registry)
            returned = core.SemanticPipeline().extract_article(
                raw,
                topic_id="economy",
                extractor=object(),
            )

        self.assertEqual(tuple(item.event_id for item in returned.events), (event.event_id,))
        canonical = registry.canonical_event(event.event_id)
        self.assertEqual(canonical.actor, "한국은행 금융통화위원회")
        self.assertEqual(canonical.action, "기준금리를 결정한다")
        self.assertTrue(canonical.evidence_refs)
        self.assertEqual(authority.calls, [event.event_id])

        projected = core.event_understanding_decision(
            event,
            facts={},
            evidence={},
            morphology=None,
            now=NOW,
        )
        self.assertIs(projected.status, UnderstandingStatus.RESOLVED)
        self.assertTrue(projected.publishable_event)

    def test_unresolved_event_is_retained_for_source_resolution_without_canonical_or_authority(self) -> None:
        raw = _article(
            "unresolved",
            "이들 투자자의 부담이 가중된다.",
        )
        result, event = _semantic_result(
            raw,
            subject="이들 투자자",
            action="부담이 가중된다",
        )
        registry = ProductionV2Registry()
        authority = _RecordingAuthority(registry)
        core = SimpleNamespace(
            SemanticPipeline=object,
            event_understanding_decision=object(),
            _INSIGHT_DESK_V2_AUTHORITATIVE_OWNER=authority,
        )

        class FakeLegacySemanticPipeline:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def extract_article(self, _article, *, topic_id: str, extractor):
                del topic_id, extractor
                return result

        with (
            mock.patch.object(lifecycle_module, "LegacySemanticPipeline", FakeLegacySemanticPipeline),
            mock.patch.object(lifecycle_module, "_optional_morphology", return_value=None),
        ):
            install_event_understanding_lifecycle(core, registry)
            returned = core.SemanticPipeline().extract_article(
                raw,
                topic_id="economy",
                extractor=object(),
            )

        self.assertEqual(tuple(item.event_id for item in returned.events), (event.event_id,))
        self.assertNotIn(event.event_id, registry.events_by_id)
        self.assertEqual(authority.calls, [])
        projected = core.event_understanding_decision(
            event,
            facts={},
            evidence={},
            morphology=None,
            now=NOW,
        )
        self.assertIs(projected.status, UnderstandingStatus.UNRESOLVED)
        self.assertFalse(projected.publishable_event)

    def test_runtime_replaces_legacy_per_event_judge_with_projection_and_restores_it(self) -> None:
        original_pipeline = production._core.SemanticPipeline
        original_understanding = production._core.event_understanding_decision
        with production_v2_runtime(production._core):
            self.assertIsNot(production._core.SemanticPipeline, original_pipeline)
            self.assertEqual(
                production._core.SemanticPipeline.__module__,
                "insight_desk.production_event_understanding_lifecycle_v2",
            )
            self.assertIsNot(
                production._core.event_understanding_decision,
                original_understanding,
            )
            self.assertEqual(
                production._core.event_understanding_decision.__module__,
                "insight_desk.production_event_understanding_lifecycle_v2",
            )
        self.assertIs(production._core.SemanticPipeline, original_pipeline)
        self.assertIs(production._core.event_understanding_decision, original_understanding)


if __name__ == "__main__":
    unittest.main()
