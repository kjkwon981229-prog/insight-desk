from __future__ import annotations

import unittest

from insight_desk.core import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    ContractError,
    PipelineResponsibility,
    TopicRelation,
    UnderstandingStatus,
    owner_for,
    validate_owner_boundaries,
)


class EventUnderstandingContractV2Tests(unittest.TestCase):
    def test_resolved_understanding_requires_a_primary_event(self) -> None:
        draft = CanonicalEventDraft(
            draft_id="draft:context",
            topic="economy",
            actor="한국은행",
            action="과거 정책 배경을 설명했다",
            event_type="background_context",
            source_ids=("source:1",),
            evidence_ids=("evidence:1",),
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            understanding_status=UnderstandingStatus.RESOLVED,
        )
        with self.assertRaisesRegex(ContractError, "primary event"):
            ArticleUnderstanding(
                understanding_id="understanding:1",
                topic="economy",
                source_ids=("source:1",),
                event_drafts=(draft,),
                status=UnderstandingStatus.RESOLVED,
            )

    def test_unresolved_understanding_is_first_class_not_drop(self) -> None:
        result = ArticleUnderstanding(
            understanding_id="understanding:uncertain",
            topic="economy",
            source_ids=("source:1",),
            event_drafts=(),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("conflicting_source_meaning",),
        )
        self.assertEqual(result.status, UnderstandingStatus.UNRESOLVED)
        self.assertEqual(result.event_drafts, ())

    def test_unresolved_event_draft_requires_reason(self) -> None:
        with self.assertRaisesRegex(ContractError, "requires uncertainty reasons"):
            CanonicalEventDraft(
                draft_id="draft:uncertain",
                topic="economy",
                actor="한국은행",
                action="정책 방향을 설명했다",
                event_type="policy_statement",
                source_ids=("source:1",),
                evidence_ids=("evidence:1",),
                article_role=ArticleEventRole.PRIMARY,
                topic_relation=TopicRelation.UNRESOLVED,
                understanding_status=UnderstandingStatus.UNRESOLVED,
            )

    def test_draft_preserves_semantic_role_topic_relation_and_evidence_lineage(self) -> None:
        draft = CanonicalEventDraft(
            draft_id="draft:bok-rate",
            topic="economy",
            actor="한국은행 금융통화위원회",
            action="기준금리를 결정했다",
            object="기준금리",
            event_type="rate_decision",
            source_ids=("source:bok",),
            evidence_ids=("evidence:bok-rate",),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.RESOLVED,
            event_time="2026-08-27",
            metric="기준금리",
            value="2.50",
            unit="%",
            attribution="한국은행 금융통화위원회",
        )
        result = ArticleUnderstanding(
            understanding_id="understanding:bok",
            topic="economy",
            source_ids=("source:bok",),
            event_drafts=(draft,),
            status=UnderstandingStatus.RESOLVED,
        )
        self.assertEqual(result.event_drafts[0].article_role, ArticleEventRole.PRIMARY)
        self.assertEqual(result.event_drafts[0].topic_relation, TopicRelation.DIRECT)
        self.assertEqual(result.event_drafts[0].evidence_ids, ("evidence:bok-rate",))

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
