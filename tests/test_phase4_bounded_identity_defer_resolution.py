from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from insight_desk.acquisition import ArticleCandidate
from insight_desk.core import CandidateEvent, EventFact, RawArticle, SourceProvenance
from insight_desk.production_orchestrator_v2 import (
    CanonicalIdentityEngine,
    ProductionV2Registry,
    canonical_event_from_candidate,
    source_document_from_article,
)


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


class BoundedIdentityDeferResolutionTests(unittest.TestCase):
    def test_identity_owner_uses_one_bounded_source_expansion_without_claim_verifiers(self) -> None:
        shared_body = (
            "한국은행이 29일 금융통계를 발표했다. 가계대출 금리는 4.64%를 기록했다."
        )
        left_raw = _article("article:left", shared_body, url="https://left.example/a")
        right_raw = _article("article:right", shared_body, url="https://right.example/a")
        left_event, left_fact = _event(left_raw, "left")
        right_event, right_fact = _event(right_raw, "right")

        registry = ProductionV2Registry()
        for raw, event, fact in (
            (left_raw, left_event, left_fact),
            (right_raw, right_event, right_fact),
        ):
            source = source_document_from_article(raw)
            registry.sources_by_article[raw.article_id] = source
            registry.events_by_id[event.event_id] = canonical_event_from_candidate(
                event,
                facts={fact.fact_id: fact},
                source=source,
            )

        discovery = _Discovery()
        acquisition = _Acquisition(shared_body)
        owner = CanonicalIdentityEngine(registry)
        judgment = owner.resolve_deferred(
            left_event,
            right_event,
            discovery=discovery,
            acquisition=acquisition,
            topic_id="economy",
        )

        self.assertTrue(judgment.same_event)
        self.assertEqual(judgment.primary_checks, 0)
        self.assertEqual(judgment.secondary_checks, 0)
        self.assertEqual(len(discovery.calls), 1)
        self.assertEqual(discovery.calls[0][2], 3)
        self.assertLessEqual(acquisition.calls, 2)

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
