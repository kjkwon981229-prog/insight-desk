from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from insight_desk.acquisition import ArticleCandidate
from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.production_identity_resolution_v2 import CanonicalIdentityResolutionLane
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_orchestrator_compat_v2 import source_document_from_article


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _article(article_id: str, body: str, *, url: str) -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id=f"web:{article_id}",
            source_name="example.com",
            url=url,
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="한국은행 금융통계 발표",
        body=body,
        topic_ids=("economy",),
        query="한국은행 금융통계",
    )


def _event(raw: RawArticle, suffix: str) -> tuple[CandidateEvent, EventFact]:
    evidence_id = f"evidence:{suffix}"
    fact = EventFact(
        fact_id=f"fact:{suffix}",
        subject="한국은행",
        action="금융통계를 발표했다",
        object="가계대출 금리",
        evidence_ids=(evidence_id,),
        event_date="2026-08-29",
    )
    event = CandidateEvent(
        event_id=f"event:{suffix}",
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(raw.article_id,),
    )
    return event, fact


def _canonical(event: CandidateEvent, fact: EventFact, source_id: str) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event.event_id,
        topic=event.topic_id,
        actor=fact.subject,
        action=fact.action,
        object=fact.object,
        event_type="news_event",
        source_ids=(source_id,),
        event_time=fact.event_date,
        publication_time=NOW,
        fact_ids=(fact.fact_id,),
        evidence_ids=fact.evidence_ids,
    )


class _Discovery:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def search(self, query: str, *, topic_id: str, limit: int = 10):
        self.calls.append((query, topic_id, limit))
        return tuple(
            ArticleCandidate(
                candidate_id=f"bridge-{index}",
                url=f"https://bridge.example/{index}",
                search_title="한국은행 금융통계 발표",
                source_name="bridge.example",
                published_at=NOW,
                topic_ids=(topic_id,),
                query=query,
                retrieved_via="fixture",
            )
            for index in range(5)
        )


class _Acquisition:
    def __init__(self, body: str) -> None:
        self.body = body
        self.calls = 0

    def acquire(self, candidate: ArticleCandidate):
        self.calls += 1
        raw = _article(
            f"article:bridge:{self.calls}",
            self.body,
            url=candidate.url,
        )
        return SimpleNamespace(article=raw)


class _BridgeUnderstandingOwner:
    def __init__(self, *, resolved: bool) -> None:
        self.resolved = resolved
        self.calls: list[str] = []

    def identity_bridge_events(self, article, *, topic_id: str):
        self.calls.append(article.article_id)
        if not self.resolved:
            return ()
        return (
            CanonicalEvent(
                event_id=f"event:bridge:{article.article_id}",
                topic=topic_id,
                actor="한국은행",
                action="금융통계를 발표했다",
                object="가계대출 금리",
                event_type="news_event",
                source_ids=(f"source-document:{article.article_id}",),
                event_time="2026-08-29",
                publication_time=NOW,
            ),
        )


class BoundedIdentityDeferResolutionTests(unittest.TestCase):
    def _registry_pair(self):
        left_raw = _article(
            "article:left",
            "원문 A",
            url="https://left.example/a",
        )
        right_raw = _article(
            "article:right",
            "원문 B",
            url="https://right.example/a",
        )
        left_event, left_fact = _event(left_raw, "left")
        right_event, right_fact = _event(right_raw, "right")

        registry = ProductionV2Registry()
        for raw, event, fact in (
            (left_raw, left_event, left_fact),
            (right_raw, right_event, right_fact),
        ):
            source = source_document_from_article(raw)
            registry.sources_by_article[raw.article_id] = source
            registry.events_by_id[event.event_id] = _canonical(event, fact, source.source_id)
        return registry, left_event, right_event

    def test_identity_lane_resolves_only_through_event_understanding_canonical_bridge(self) -> None:
        registry, left_event, right_event = self._registry_pair()
        before_sources = dict(registry.sources_by_article)
        before_events = dict(registry.events_by_id)

        discovery = _Discovery()
        acquisition = _Acquisition(
            "이 본문 문자열 자체는 Identity owner가 읽거나 비교해서는 안 된다."
        )
        understanding = _BridgeUnderstandingOwner(resolved=True)
        lane = CanonicalIdentityResolutionLane(registry, understanding)
        judgment = lane.resolve(
            left_event,
            right_event,
            discovery=discovery,
            acquisition=acquisition,
            topic_id="economy",
        )

        self.assertTrue(judgment.same_event)
        self.assertEqual(judgment.reason, "canonical_same_event:event_understanding_bridge")
        self.assertEqual(judgment.primary_checks, 0)
        self.assertEqual(judgment.secondary_checks, 0)
        self.assertEqual(len(discovery.calls), 1)
        self.assertEqual(discovery.calls[0][2], 3)
        self.assertLessEqual(acquisition.calls, 2)
        self.assertTrue(understanding.calls)
        self.assertEqual(registry.sources_by_article, before_sources)
        self.assertEqual(registry.events_by_id, before_events)

    def test_unresolved_bridge_understanding_preserves_defer(self) -> None:
        registry, left_event, right_event = self._registry_pair()
        discovery = _Discovery()
        acquisition = _Acquisition("추가 기사도 사건을 확정하기 어렵다.")
        understanding = _BridgeUnderstandingOwner(resolved=False)
        lane = CanonicalIdentityResolutionLane(registry, understanding)

        judgment = lane.resolve(
            left_event,
            right_event,
            discovery=discovery,
            acquisition=acquisition,
            topic_id="economy",
        )

        self.assertIsNone(judgment.same_event)
        self.assertEqual(
            judgment.reason,
            "canonical_identity_defer:bounded_source_expansion_exhausted",
        )
        self.assertTrue(understanding.calls)

    def test_identity_resolution_source_has_no_raw_text_semantic_authority(self) -> None:
        source = Path("insight_desk/production_identity_resolution_v2.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("visible_event_redundant", source)
        self.assertNotIn("_source_matches_event", source)
        self.assertNotIn("bridge_body", source)
        self.assertNotIn(".body", source)
        self.assertIn("identity_bridge_events(", source)
        self.assertIn("bridge_corroborates_same_event", source)

    def test_runtime_shares_the_installed_event_understanding_owner_with_identity_lane(self) -> None:
        source = Path("insight_desk/production_runtime_v2.py").read_text(encoding="utf-8")
        self.assertIn(
            "event_understanding_owner = install_event_understanding_lifecycle(core_module, registry)",
            source,
        )
        self.assertIn(
            "CanonicalIdentityResolutionLane(\n            registry,\n            event_understanding_owner,\n        )",
            source,
        )

    def test_daily_loop_resolves_defer_before_final_hold_with_per_topic_budget(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("MAX_IDENTITY_DEFER_RESOLUTION_ATTEMPTS_PER_TOPIC = 2", source)
        self.assertIn("resolve_deferred_identity(", source)
        resolution = source.index("resolve_deferred_identity(")
        final_defer = source.index('reason="identity_unresolved"', resolution)
        self.assertLess(resolution, final_defer)
        call_block = source[resolution:final_defer]
        self.assertNotIn("primary_verifier", call_block)
        self.assertNotIn("secondary_verifier", call_block)


if __name__ == "__main__":
    unittest.main()
