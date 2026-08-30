from __future__ import annotations

from datetime import datetime, timezone
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
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.production_event_understanding_compat_v2 import (
    CompatibilityEventUnderstandingDecision,
)
from insight_desk.production_event_understanding_lifecycle_v2 import (
    ProductionEventUnderstandingLifecycleOwner,
)
import insight_desk.production_event_understanding_lifecycle_v2 as lifecycle_module
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.semantic.pipeline import SemanticArticleResult


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


class _ForbiddenAuthority:
    def enrich(self, *_args, **_kwargs):
        raise AssertionError("identity bridge must not invoke authoritative enrichment")


class IdentityBridgeEventUnderstandingOwnerTests(unittest.TestCase):
    def test_identity_bridge_is_resolved_by_same_owner_but_remains_ephemeral(self) -> None:
        article = RawArticle(
            article_id="article:bridge",
            provenance=SourceProvenance(
                source_id="web:bridge",
                source_name="bridge.example",
                url="https://bridge.example/a",
                retrieved_via="fixture",
                fetched_at=NOW,
                published_at=NOW,
            ),
            title="한국은행 금융통계 발표",
            body="한국은행이 금융통계를 발표했다.",
            topic_ids=("economy",),
            query="한국은행 금융통계",
        )
        evidence = EvidenceSpan.from_article(
            evidence_id="evidence:bridge",
            article=article,
            field=EvidenceField.BODY,
            start=0,
            end=len(article.body),
        )
        fact = EventFact(
            fact_id="fact:bridge",
            subject="한국은행",
            action="금융통계를 발표했다",
            object="가계대출 금리",
            evidence_ids=(evidence.evidence_id,),
            event_date="2026-08-30",
        )
        event = CandidateEvent(
            event_id="event:bridge",
            topic_id="economy",
            fact_ids=(fact.fact_id,),
            article_ids=(article.article_id,),
        )
        semantic_result = SemanticArticleResult(
            article_id=article.article_id,
            extractor_id="fixture",
            evidence=(evidence,),
            facts=(fact,),
            events=(event,),
        )
        decision = CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            publishable_event=True,
        )

        class _FakeLegacySemanticPipeline:
            def extract_article(self, _article, *, topic_id: str, extractor):
                self_seen = (_article.article_id, topic_id, extractor)
                if self_seen[0] != article.article_id or self_seen[1] != "economy":
                    raise AssertionError("bridge extraction received the wrong article/topic")
                return semantic_result

        registry = ProductionV2Registry()
        with (
            mock.patch.object(lifecycle_module, "_optional_morphology", return_value=None),
            mock.patch.object(lifecycle_module, "LegacySemanticPipeline", _FakeLegacySemanticPipeline),
            mock.patch.object(
                lifecycle_module,
                "assess_compatibility_article_understanding",
                return_value={event.event_id: decision},
            ),
        ):
            owner = ProductionEventUnderstandingLifecycleOwner(
                registry,
                _ForbiddenAuthority(),
            )
            extractor = object()
            owner.bind_extractor(extractor)
            canonicals = owner.identity_bridge_events(article, topic_id="economy")

        self.assertEqual(len(canonicals), 1)
        canonical = canonicals[0]
        self.assertEqual(canonical.actor, "한국은행")
        self.assertEqual(canonical.action, "금융통계를 발표했다")
        self.assertEqual(canonical.object, "가계대출 금리")
        self.assertEqual(canonical.source_ids, ("source-document:article:bridge",))
        self.assertEqual(registry.sources_by_article, {})
        self.assertEqual(registry.events_by_id, {})
        self.assertEqual(registry.authoritative_facts_by_id, {})
        self.assertEqual(owner.decisions_by_event, {})

    def test_identity_bridge_without_bound_production_extractor_stays_unresolved(self) -> None:
        registry = ProductionV2Registry()
        with mock.patch.object(lifecycle_module, "_optional_morphology", return_value=None):
            owner = ProductionEventUnderstandingLifecycleOwner(
                registry,
                _ForbiddenAuthority(),
            )
        article = mock.Mock()
        self.assertEqual(owner.identity_bridge_events(article, topic_id="economy"), ())


if __name__ == "__main__":
    unittest.main()
