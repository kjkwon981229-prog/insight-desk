from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    EventFact,
    IdentityKey,
    RawArticle,
    SourceProvenance,
    finalize_identity,
    precheck_identity,
)
from insight_desk.production_orchestrator_v2 import CanonicalIdentityEngine, ProductionV2Registry


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


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
        title="독립 기사",
        body=body,
        topic_ids=("economy",),
        query="경제",
    )


def _event(article_id: str, event_id: str, fact_id: str, evidence_id: str, *, subject: str) -> tuple[CandidateEvent, EventFact]:
    fact = EventFact(
        fact_id=fact_id,
        subject=subject,
        action="발표했다",
        object="정책",
        evidence_ids=(evidence_id,),
        event_date="2026-08-29",
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="economy",
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    return event, fact


def _canonical(event: CandidateEvent, fact: EventFact) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event.event_id,
        topic=event.topic_id,
        actor=fact.subject,
        action=fact.action,
        object=fact.object,
        event_type="news_event",
        source_ids=(f"source:{event.article_ids[0]}",),
        event_time=fact.event_date,
        fact_ids=(fact.fact_id,),
        evidence_ids=fact.evidence_ids,
    )


class IdentityDeferContractTests(unittest.TestCase):
    def test_missing_identity_judgment_remains_defer_not_different_event(self) -> None:
        precheck = precheck_identity(
            IdentityKey(subject_key="same-actor", action_key="announce"),
            IdentityKey(subject_key="same-actor", action_key="announce"),
        )

        decision = finalize_identity(precheck, llm_same_event=None)

        self.assertIsNone(decision.same_event)
        self.assertFalse(decision.deterministic_block)
        self.assertFalse(decision.llm_judgment_used)
        self.assertIn("unresolved", decision.reason)


class CanonicalIdentityVerifierSeparationTests(unittest.TestCase):
    def test_canonical_identity_owner_never_calls_claim_verification_providers(self) -> None:
        left_article = _article(
            "article:left",
            "A사는 정책 관련 내용을 발표했다.",
        )
        right_article = _article(
            "article:right",
            "A사의 후속 보도에는 정책 관련 설명이 실렸다.",
        )
        left_event, left_fact = _event(
            left_article.article_id,
            "event:left",
            "fact:left",
            "evidence:left",
            subject="A사",
        )
        right_event, right_fact = _event(
            right_article.article_id,
            "event:right",
            "fact:right",
            "evidence:right",
            subject="A사",
        )

        registry = ProductionV2Registry(
            events_by_id={
                left_event.event_id: _canonical(left_event, left_fact),
                right_event.event_id: _canonical(right_event, right_fact),
            }
        )

        owner = CanonicalIdentityEngine(registry)
        owner.precheck(
            left_event,
            right_event,
            {left_fact.fact_id: left_fact, right_fact.fact_id: right_fact},
        )

        class ForbiddenVerifier:
            verifier_id = "claim-verifier-must-not-run"
            model_id = "forbidden"

            def verify(self, **_kwargs):
                raise AssertionError("claim verification provider was reused as an identity oracle")

        judgment = owner.judge(
            left_article.body,
            right_article.body,
            primary=ForbiddenVerifier(),
            secondary=ForbiddenVerifier(),
        )

        self.assertIsNone(judgment.same_event)
        self.assertEqual(judgment.primary_checks, 0)
        self.assertEqual(judgment.secondary_checks, 0)
        self.assertEqual(registry.current_identity_relation, "defer")


if __name__ == "__main__":
    unittest.main()
