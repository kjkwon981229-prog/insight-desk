from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from insight_desk.core import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    ContractError,
    PipelineResponsibility,
    SourceDocument,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
    owner_for,
    validate_owner_boundaries,
)


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
BODY = "한국은행 금융통화위원회는 27일 기준금리를 결정했다. 배경 설명도 덧붙였다."


def source() -> SourceDocument:
    return SourceDocument(
        source_id="source:bok",
        candidate_ids=("candidate:bok",),
        publisher="한국은행",
        url="https://www.bok.or.kr/example",
        title="금융통화위원회 기준금리 결정",
        body=BODY,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


def primary_draft() -> CanonicalEventDraft:
    src = source()
    sentence = "한국은행 금융통화위원회는 27일 기준금리를 결정했다."
    return CanonicalEventDraft(
        draft_id="draft:bok-rate",
        topic="economy",
        actor="한국은행 금융통화위원회",
        action="기준금리를 결정했다",
        object="기준금리",
        event_type="rate_decision",
        source_ids=(src.source_id,),
        evidence_refs=(
            UnderstandingEvidenceRef.from_source(
                src,
                field=UnderstandingEvidenceField.BODY,
                start=0,
                end=len(sentence),
            ),
        ),
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        understanding_status=UnderstandingStatus.RESOLVED,
        event_time="2026-08-27",
        attribution="한국은행 금융통화위원회",
    )


class EventUnderstandingContractV2Tests(unittest.TestCase):
    def test_resolved_understanding_requires_a_primary_event(self) -> None:
        draft = primary_draft()
        context = CanonicalEventDraft(
            draft_id="draft:context",
            topic=draft.topic,
            actor=draft.actor,
            action="배경을 설명했다",
            event_type="background_context",
            source_ids=draft.source_ids,
            evidence_refs=draft.evidence_refs,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            understanding_status=UnderstandingStatus.RESOLVED,
        )
        with self.assertRaisesRegex(ContractError, "primary event"):
            ArticleUnderstanding(
                understanding_id="understanding:1",
                topic="economy",
                source_ids=("source:bok",),
                event_drafts=(context,),
                status=UnderstandingStatus.RESOLVED,
            )

    def test_unresolved_understanding_is_first_class_not_drop(self) -> None:
        result = ArticleUnderstanding(
            understanding_id="understanding:uncertain",
            topic="economy",
            source_ids=("source:bok",),
            event_drafts=(),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("conflicting_source_meaning",),
        )
        self.assertEqual(result.status, UnderstandingStatus.UNRESOLVED)
        self.assertEqual(result.event_drafts, ())

    def test_unresolved_event_draft_requires_reason(self) -> None:
        draft = primary_draft()
        with self.assertRaisesRegex(ContractError, "requires uncertainty reasons"):
            CanonicalEventDraft(
                draft_id="draft:uncertain",
                topic=draft.topic,
                actor=draft.actor,
                action=draft.action,
                event_type=draft.event_type,
                source_ids=draft.source_ids,
                evidence_refs=draft.evidence_refs,
                article_role=ArticleEventRole.PRIMARY,
                topic_relation=TopicRelation.UNRESOLVED,
                understanding_status=UnderstandingStatus.UNRESOLVED,
            )

    def test_evidence_ref_is_exact_source_range_not_generated_quote(self) -> None:
        src = source()
        ref = primary_draft().evidence_refs[0]
        ref.validate_against(src)
        tampered = SourceDocument(
            source_id=src.source_id,
            candidate_ids=src.candidate_ids,
            publisher=src.publisher,
            url=src.url,
            title=src.title,
            body=src.body.replace("결정했다", "유지했다"),
            fetched_at=src.fetched_at,
            publication_time=src.publication_time,
            retrieved_via=src.retrieved_via,
            content_sha256=hashlib.sha256(
                src.body.replace("결정했다", "유지했다").encode("utf-8")
            ).hexdigest(),
        )
        with self.assertRaisesRegex(ContractError, "digest differs"):
            ref.validate_against(tampered)

    def test_event_understanding_and_identity_handoff_are_explicit(self) -> None:
        validate_owner_boundaries()
        understanding = owner_for(PipelineResponsibility.EVENT_UNDERSTANDING)
        identity = owner_for(PipelineResponsibility.EVENT_IDENTITY)
        authoritative = owner_for(PipelineResponsibility.AUTHORITATIVE_ENRICHMENT)

        self.assertEqual(understanding.owner_id, "event_understanding_engine")
        self.assertEqual(understanding.output_contract, "ArticleUnderstanding")
        self.assertIn("identify_primary_and_context_events", understanding.allowed_decisions)
        self.assertIn("report_semantic_uncertainty", understanding.allowed_decisions)
        self.assertIn("resolve_event_identity", understanding.forbidden_decisions)
        self.assertEqual(authoritative.input_contract, "ArticleUnderstanding")
        self.assertEqual(authoritative.output_contract, "EnrichedEventDraftSet")
        self.assertEqual(identity.input_contract, "EnrichedEventDraftSet")
        self.assertEqual(identity.output_contract, "CanonicalEventSet")
        self.assertIn("understand_event", identity.forbidden_decisions)


if __name__ == "__main__":
    unittest.main()
