from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from insight_desk.core.canonical_v2 import (
    AuthoritativeFact,
    CanonicalEvent,
    CanonicalPublicationBundle,
    SourceDocument,
    VerifiedPublication,
)
from insight_desk.core.contracts import ContractError, RenderMode
from insight_desk.core.orchestration_v2 import (
    OWNER_BOUNDARIES,
    PipelineResponsibility,
    owner_for,
    validate_owner_boundaries,
)


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
BODY = "한국은행 금융통화위원회는 27일 기준금리를 결정하고 수정 경제전망을 발표한다."


def source(source_id: str = "source:bok-1") -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        candidate_ids=("candidate:bok-1",),
        publisher="한국은행",
        url="https://www.bok.or.kr/example",
        title="통화정책방향 관련 자료",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="official_fetch",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


def authoritative_fact() -> AuthoritativeFact:
    return AuthoritativeFact(
        fact_id="auth:bok-rate",
        provider_id="ecos",
        subject="한국은행 기준금리",
        predicate="기준금리",
        value="2.50",
        unit="%",
        effective_time="2026-08-27",
        retrieved_at=NOW,
        source_url="https://ecos.bok.or.kr/example",
    )


def parent_event() -> CanonicalEvent:
    return CanonicalEvent(
        event_id="BOK_MPC_2026-08-27",
        topic="economy",
        actor="한국은행 금융통화위원회",
        action="통화정책방향 회의를 개최한다",
        event_type="policy_meeting",
        source_ids=("source:bok-1",),
        event_time="2026-08-27",
        publication_time=NOW,
        participants=("한국은행", "금융통화위원회"),
        authoritative_fact_ids=("auth:bok-rate",),
    )


def child_event() -> CanonicalEvent:
    return CanonicalEvent(
        event_id="BOK_MPC_2026-08-27_RATE_DECISION",
        topic="economy",
        actor="한국은행 금융통화위원회",
        action="기준금리를 결정한다",
        object="기준금리",
        event_type="rate_decision",
        source_ids=("source:bok-1",),
        event_time="2026-08-27",
        publication_time=NOW,
        participants=("한국은행", "금융통화위원회"),
        metric="기준금리",
        value="2.50",
        unit="%",
        attribution="한국은행 금융통화위원회",
        parent_event_id="BOK_MPC_2026-08-27",
        authoritative_fact_ids=("auth:bok-rate",),
    )


def publication() -> VerifiedPublication:
    return VerifiedPublication(
        publication_id="publication:bok-rate-20260827",
        event_id="BOK_MPC_2026-08-27_RATE_DECISION",
        topic="economy",
        headline="한국은행 금통위, 기준금리 결정",
        summary="한국은행 금융통화위원회가 27일 기준금리를 결정한다.",
        source_ids=("source:bok-1",),
        primary_source_url="https://www.bok.or.kr/example",
        claim_ids=("claim:headline", "claim:summary"),
        verification_check_ids=("verify:headline", "verify:summary"),
        verified_at=NOW,
        render_mode=RenderMode.GENERATED,
        event_time="2026-08-27",
        publication_time=NOW,
        parent_event_id="BOK_MPC_2026-08-27",
        authoritative_fact_ids=("auth:bok-rate",),
    )


class SingleOwnerContractTests(unittest.TestCase):
    def test_every_pipeline_responsibility_has_exactly_one_owner(self) -> None:
        validate_owner_boundaries()
        self.assertEqual(
            {item.responsibility for item in OWNER_BOUNDARIES},
            set(PipelineResponsibility),
        )
        self.assertEqual(len(OWNER_BOUNDARIES), len(PipelineResponsibility))

    def test_identity_owner_does_not_own_relevance_quality_generation_or_verification(self) -> None:
        identity = owner_for(PipelineResponsibility.EVENT_IDENTITY)
        self.assertEqual(identity.owner_id, "canonical_identity_engine")
        for forbidden in (
            "judge_relevance",
            "judge_story_quality",
            "generate_copy",
            "verify_claims",
        ):
            self.assertIn(forbidden, identity.forbidden_decisions)

    def test_verifier_cannot_deduplicate_or_resolve_event_identity(self) -> None:
        verifier = owner_for(PipelineResponsibility.VERIFICATION)
        self.assertIn("resolve_event_identity", verifier.forbidden_decisions)
        self.assertIn("deduplicate_events", verifier.forbidden_decisions)

    def test_publication_renderer_push_and_execution_are_mechanical_only(self) -> None:
        for responsibility in (
            PipelineResponsibility.PUBLICATION_CONTRACT,
            PipelineResponsibility.RENDERING,
            PipelineResponsibility.PUSH,
            PipelineResponsibility.EXECUTION,
        ):
            boundary = owner_for(responsibility)
            self.assertTrue(boundary.mechanical_only)
            self.assertFalse(boundary.semantic_authority)

    def test_event_understanding_does_not_decide_identity_or_publication_selection(self) -> None:
        understanding = owner_for(PipelineResponsibility.EVENT_UNDERSTANDING)
        self.assertIn("resolve_event_identity", understanding.forbidden_decisions)
        self.assertIn("select_publication_card", understanding.forbidden_decisions)


class CanonicalEventContractTests(unittest.TestCase):
    def test_valid_parent_child_publication_preserves_event_identity_and_provenance(self) -> None:
        bundle = CanonicalPublicationBundle(
            sources=(source(),),
            authoritative_facts=(authoritative_fact(),),
            events=(parent_event(), child_event()),
            publications=(publication(),),
        )
        bundle.validate()

        published = bundle.publications[0]
        child = bundle.events[1]
        self.assertEqual(published.event_id, child.event_id)
        self.assertEqual(published.parent_event_id, child.parent_event_id)
        self.assertEqual(published.source_ids, child.source_ids)
        self.assertEqual(published.authoritative_fact_ids, child.authoritative_fact_ids)
        self.assertEqual(published.event_time, child.event_time)
        self.assertEqual(published.publication_time, child.publication_time)

    def test_event_cannot_be_its_own_parent(self) -> None:
        with self.assertRaisesRegex(ContractError, "own parent"):
            CanonicalEvent(
                event_id="event:self",
                topic="economy",
                actor="한국은행",
                action="발표한다",
                event_type="announcement",
                source_ids=("source:1",),
                parent_event_id="event:self",
            )

    def test_metric_and_value_must_travel_together(self) -> None:
        with self.assertRaisesRegex(ContractError, "metric requires value"):
            CanonicalEvent(
                event_id="event:metric",
                topic="economy",
                actor="한국은행",
                action="결정한다",
                event_type="rate_decision",
                source_ids=("source:1",),
                metric="기준금리",
            )
        with self.assertRaisesRegex(ContractError, "value requires metric"):
            CanonicalEvent(
                event_id="event:value",
                topic="economy",
                actor="한국은행",
                action="결정한다",
                event_type="rate_decision",
                source_ids=("source:1",),
                value="2.50",
            )

    def test_event_time_is_iso_date_or_offset_aware_datetime(self) -> None:
        CanonicalEvent(
            event_id="event:date",
            topic="economy",
            actor="한국은행",
            action="결정한다",
            event_type="rate_decision",
            source_ids=("source:1",),
            event_time="2026-08-27",
        )
        with self.assertRaisesRegex(ContractError, "ISO-8601"):
            CanonicalEvent(
                event_id="event:bad-date",
                topic="economy",
                actor="한국은행",
                action="결정한다",
                event_type="rate_decision",
                source_ids=("source:1",),
                event_time="오늘",
            )

    def test_publication_cannot_introduce_source_outside_canonical_event(self) -> None:
        rogue_source = source("source:rogue")
        event = child_event()
        rogue_publication = VerifiedPublication(
            publication_id="publication:rogue",
            event_id=event.event_id,
            topic=event.topic,
            headline="한국은행 기준금리 결정",
            summary="한국은행이 기준금리를 결정한다.",
            source_ids=(rogue_source.source_id,),
            primary_source_url=rogue_source.url,
            claim_ids=("claim:1",),
            verification_check_ids=("verify:1",),
            verified_at=NOW,
            render_mode=RenderMode.GENERATED,
            event_time=event.event_time,
            publication_time=event.publication_time,
            parent_event_id=event.parent_event_id,
            authoritative_fact_ids=event.authoritative_fact_ids,
        )
        bundle = CanonicalPublicationBundle(
            sources=(source(), rogue_source),
            authoritative_facts=(authoritative_fact(),),
            events=(parent_event(), event),
            publications=(rogue_publication,),
        )
        with self.assertRaisesRegex(ContractError, "outside canonical event"):
            bundle.validate()

    def test_publication_cannot_mutate_parent_event_or_time(self) -> None:
        event = child_event()
        mutated = VerifiedPublication(
            publication_id="publication:mutated",
            event_id=event.event_id,
            topic=event.topic,
            headline="한국은행 기준금리 결정",
            summary="한국은행이 기준금리를 결정한다.",
            source_ids=event.source_ids,
            primary_source_url="https://www.bok.or.kr/example",
            claim_ids=("claim:1",),
            verification_check_ids=("verify:1",),
            verified_at=NOW,
            render_mode=RenderMode.GENERATED,
            event_time="2026-08-28",
            publication_time=event.publication_time,
            parent_event_id=event.parent_event_id,
            authoritative_fact_ids=event.authoritative_fact_ids,
        )
        bundle = CanonicalPublicationBundle(
            sources=(source(),),
            authoritative_facts=(authoritative_fact(),),
            events=(parent_event(), event),
            publications=(mutated,),
        )
        with self.assertRaisesRegex(ContractError, "event_time differs"):
            bundle.validate()

    def test_source_document_requires_byte_binding_digest(self) -> None:
        with self.assertRaisesRegex(ContractError, "SHA-256"):
            SourceDocument(
                source_id="source:bad",
                candidate_ids=("candidate:bad",),
                publisher="Example",
                url="https://example.com/article",
                title="Example",
                body="body",
                fetched_at=NOW,
                publication_time=NOW,
                retrieved_via="test",
                content_sha256="not-a-digest",
            )


if __name__ == "__main__":
    unittest.main()
