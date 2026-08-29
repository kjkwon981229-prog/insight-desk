from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, CanonicalEvent, EventFact
from insight_desk.core.identity import IdentityDisposition, identity_disposition
from insight_desk.production_orchestrator_v2 import CanonicalIdentityEngine, ProductionV2Registry


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _candidate(event_id: str, fact_id: str, article_id: str) -> CandidateEvent:
    return CandidateEvent(
        event_id=event_id,
        topic_id="economy",
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )


def _fact(fact_id: str, *, actor: str, day: str) -> EventFact:
    return EventFact(
        fact_id=fact_id,
        subject=actor,
        action="기준금리를 결정한다",
        object="기준금리",
        evidence_ids=(f"evidence:{fact_id}",),
        event_date=day,
    )


def _canonical(
    event_id: str,
    *,
    actor: str,
    day: str,
    action: str = "기준금리를 결정한다",
    object: str = "기준금리",
) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        topic="economy",
        actor=actor,
        action=action,
        object=object,
        event_type="news_event",
        source_ids=(f"source:{event_id}",),
        event_time=day,
        publication_time=NOW,
        participants=("한국은행", "금융통화위원회"),
    )


class CanonicalOnlyIdentityOwnerTests(unittest.TestCase):
    def test_identity_owner_source_contains_no_raw_body_or_legacy_candidate_identity_authority(self) -> None:
        source = Path("insight_desk/production_orchestrator_v2.py").read_text(encoding="utf-8")
        owner = source[source.index("class CanonicalIdentityEngine:"):source.index("def _evidence_integrity_assessment", source.index("class CanonicalIdentityEngine:"))]
        self.assertNotIn(".body", owner)
        self.assertNotIn("legacy_compare_candidate_identity", owner)
        self.assertNotIn("legacy_visible_event_redundant", owner)
        self.assertNotIn("legacy_resolve_candidate_pair", owner)

    def test_explicit_canonical_date_conflict_blocks_merge_without_fact_semantics(self) -> None:
        left = _candidate("event:left", "fact:left", "article:left")
        right = _candidate("event:right", "fact:right", "article:right")
        registry = ProductionV2Registry(
            events_by_id={
                left.event_id: _canonical(left.event_id, actor="한국은행", day="2026-08-29"),
                right.event_id: _canonical(right.event_id, actor="한국은행", day="2026-08-30"),
            }
        )
        owner = CanonicalIdentityEngine(registry)
        decision = owner.precheck(left, right, {})
        self.assertTrue(decision.deterministic_block)
        self.assertFalse(decision.same_event)
        self.assertEqual(identity_disposition(decision), IdentityDisposition.DIFFERENT_EVENT)

    def test_same_scheduled_bok_policy_meeting_binds_outlook_child_from_canonical_fields_only(self) -> None:
        left = _candidate("event:left", "fact:left", "article:left")
        right = _candidate("event:right", "fact:right", "article:right")
        registry = ProductionV2Registry(
            events_by_id={
                left.event_id: _canonical(
                    left.event_id,
                    actor="한국은행 금융통화위원회",
                    day="2026-08-29",
                    action="기준금리를 결정한다",
                    object="기준금리",
                ),
                right.event_id: _canonical(
                    right.event_id,
                    actor="한국은행",
                    day="2026-08-29",
                    action="수정 경제전망과 향후 6개월 점도표를 공개한다",
                    object="수정 경제전망과 기준금리 전망 점도표",
                ),
            }
        )
        owner = CanonicalIdentityEngine(registry)
        precheck = owner.precheck(left, right, {})
        self.assertFalse(precheck.deterministic_block)

        class ForbiddenVerifier:
            verifier_id = "forbidden"
            model_id = "forbidden"
            def verify(self, **_kwargs):
                raise AssertionError("claim verifier must not run")

        judgment = owner.judge("ignored raw text", "ignored raw text", primary=ForbiddenVerifier(), secondary=ForbiddenVerifier())
        self.assertTrue(judgment.same_event)
        self.assertEqual(judgment.primary_checks, 0)
        self.assertEqual(judgment.secondary_checks, 0)
        self.assertEqual(registry.current_identity_relation, "parent_child")
        self.assertEqual(
            registry.canonical_event(left.event_id).parent_event_id,
            registry.canonical_event(right.event_id).parent_event_id,
        )

    def test_unresolved_canonical_pair_stays_defer_and_resolve_does_not_reinvoke_legacy_identity(self) -> None:
        left = _candidate("event:left", "fact:left", "article:left")
        right = _candidate("event:right", "fact:right", "article:right")
        registry = ProductionV2Registry(
            events_by_id={
                left.event_id: _canonical(left.event_id, actor="A사", day="2026-08-29", action="정책을 발표했다"),
                right.event_id: _canonical(right.event_id, actor="A사", day="2026-08-29", action="정책을 발표했다"),
            }
        )
        owner = CanonicalIdentityEngine(registry)
        precheck = owner.precheck(left, right, {})
        self.assertIsNone(precheck.same_event)

        judgment = owner.judge("ignored", "ignored", primary=object(), secondary=object())
        self.assertIsNone(judgment.same_event)
        resolution = owner.resolve(left, right, {}, semantic_same_event=judgment.same_event)
        self.assertIsNone(resolution.decision.same_event)
        self.assertEqual(identity_disposition(resolution.decision), IdentityDisposition.DEFER)
        self.assertEqual(len(resolution.events), 2)


if __name__ == "__main__":
    unittest.main()
