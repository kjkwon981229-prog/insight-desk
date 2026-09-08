from __future__ import annotations

import unittest
from dataclasses import fields
from datetime import datetime, timezone

from insight_desk.core import (
    CandidateEvent,
    Certainty,
    ContractBundle,
    ContractError,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    FailureKind,
    PipelineStage,
    RawArticle,
    RecoveryAction,
    RenderMode,
    RenderedBriefing,
    RenderedEntry,
    SourceProvenance,
    TemporalState,
    VerificationCheck,
    VerificationVerdict,
    VerifiedClaim,
    recovery_action,
)


class CoreContractTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        self.article = RawArticle(
            article_id="article-1",
            provenance=SourceProvenance(
                source_id="source-1",
                source_name="Example News",
                url="https://example.com/article-1",
                retrieved_via="naver_search_then_direct_fetch",
                fetched_at=now,
                published_at=now,
            ),
            title="A사, AI 사업 투자 완료",
            body="A사가 AI 사업에 투자했다.",
            topic_ids=("ai_tech",),
            query="AI 투자",
        )
        self.evidence = EvidenceSpan.from_article(
            evidence_id="evidence-1",
            article=self.article,
            field=EvidenceField.BODY,
            start=0,
            end=len(self.article.body),
        )
        self.fact = EventFact(
            fact_id="fact-1",
            subject="A사",
            action="투자",
            object="AI 사업",
            temporal_state=TemporalState.COMPLETED,
            certainty=Certainty.ASSERTED,
            evidence_ids=(self.evidence.evidence_id,),
        )
        self.event = CandidateEvent(
            event_id="event-1",
            topic_id="ai_tech",
            fact_ids=(self.fact.fact_id,),
            article_ids=(self.article.article_id,),
        )
        self.check = VerificationCheck(
            check_id="check-1",
            verifier_id="cloudflare_workers_ai_free",
            model_id="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            evidence_ids=(self.evidence.evidence_id,),
            entailed=True,
        )
        self.claim = VerifiedClaim(
            claim_id="claim-1",
            event_id=self.event.event_id,
            text="A사가 AI 사업에 투자했다.",
            evidence_ids=(self.evidence.evidence_id,),
            checks=(self.check,),
            verdict=VerificationVerdict.SUPPORTED,
        )

    def test_valid_bundle_preserves_provenance_end_to_end(self) -> None:
        briefing = RenderedBriefing(
            briefing_id="briefing-1",
            generated_at=datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc),
            entries=(
                RenderedEntry(
                    event_id=self.event.event_id,
                    headline="A사, AI 사업 투자 완료",
                    summary=self.claim.text,
                    claim_ids=(self.claim.claim_id,),
                    render_mode=RenderMode.GENERATED,
                ),
            ),
        )
        bundle = ContractBundle(
            articles=(self.article,),
            evidence=(self.evidence,),
            facts=(self.fact,),
            events=(self.event,),
            claims=(self.claim,),
            briefing=briefing,
        )
        bundle.validate()

    def test_evidence_must_still_match_the_exact_source_text(self) -> None:
        tampered = EvidenceSpan(
            evidence_id="evidence-1",
            article_id=self.article.article_id,
            field=EvidenceField.BODY,
            start=0,
            end=len(self.article.body),
            text="B사가 AI 사업에 투자했다.",
        )
        bundle = ContractBundle(articles=(self.article,), evidence=(tampered,))
        with self.assertRaises(ContractError):
            bundle.validate()

    def test_non_supported_claim_cannot_be_published(self) -> None:
        inconclusive_check = VerificationCheck(
            check_id="check-error",
            verifier_id="cloudflare_workers_ai_free",
            model_id="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            evidence_ids=(self.evidence.evidence_id,),
            entailed=None,
            error_code="FREE_QUOTA_EXHAUSTED",
        )
        claim = VerifiedClaim(
            claim_id="claim-indeterminate",
            event_id=self.event.event_id,
            text="A사가 AI 사업에 투자했다.",
            evidence_ids=(self.evidence.evidence_id,),
            checks=(inconclusive_check,),
            verdict=VerificationVerdict.INDETERMINATE,
        )
        briefing = RenderedBriefing(
            briefing_id="briefing-1",
            generated_at=datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc),
            entries=(
                RenderedEntry(
                    event_id=self.event.event_id,
                    headline="A사 AI 투자",
                    summary=claim.text,
                    claim_ids=(claim.claim_id,),
                    render_mode=RenderMode.EXTRACTIVE_FALLBACK,
                ),
            ),
        )
        bundle = ContractBundle(
            articles=(self.article,),
            evidence=(self.evidence,),
            facts=(self.fact,),
            events=(self.event,),
            claims=(claim,),
            briefing=briefing,
        )
        with self.assertRaises(ContractError):
            bundle.validate()

    def test_paid_verifier_result_is_rejected_by_contract(self) -> None:
        with self.assertRaises(ContractError):
            VerificationCheck(
                check_id="paid-check",
                verifier_id="paid-provider",
                model_id="paid-model",
                evidence_ids=(self.evidence.evidence_id,),
                entailed=True,
                zero_cost=False,
            )

    def test_event_fact_has_no_legacy_event_type_field(self) -> None:
        self.assertNotIn("event_type", {item.name for item in fields(EventFact)})


class FailurePolicyTests(unittest.TestCase):
    def test_generation_failure_never_deletes_a_valid_event(self) -> None:
        decisions = [
            recovery_action(
                PipelineStage.GENERATION,
                FailureKind.INVALID_OUTPUT,
                attempts=attempt,
            )
            for attempt in range(3)
        ]
        self.assertEqual(
            [decision.action for decision in decisions],
            [
                RecoveryAction.RETRY_FREE_PROVIDER,
                RecoveryAction.TRY_ALTERNATE_FREE_PROVIDER,
                RecoveryAction.USE_EXTRACTIVE_FALLBACK,
            ],
        )
        self.assertTrue(all(decision.preserves_existing_event for decision in decisions))
        self.assertTrue(all(not decision.global_abort for decision in decisions))

    def test_ambiguous_identity_fails_safe_by_not_merging(self) -> None:
        decision = recovery_action(
            PipelineStage.EVENT_IDENTITY,
            FailureKind.IDENTITY_AMBIGUOUS,
        )
        self.assertEqual(decision.action, RecoveryAction.KEEP_EVENTS_SEPARATE)
        self.assertTrue(decision.preserves_existing_event)

    def test_verifier_outage_falls_back_local_then_indeterminate(self) -> None:
        first = recovery_action(
            PipelineStage.CLAIM_VERIFICATION,
            FailureKind.FREE_QUOTA_EXHAUSTED,
            attempts=0,
        )
        second = recovery_action(
            PipelineStage.CLAIM_VERIFICATION,
            FailureKind.FREE_QUOTA_EXHAUSTED,
            attempts=1,
        )
        self.assertEqual(first.action, RecoveryAction.USE_LOCAL_SECONDARY_VERIFIER)
        self.assertEqual(second.action, RecoveryAction.MARK_CLAIM_INDETERMINATE)
        self.assertTrue(first.preserves_existing_event)
        self.assertTrue(second.preserves_existing_event)

    def test_recovery_action_enum_contains_no_paid_path(self) -> None:
        self.assertFalse(any("paid" in action.value for action in RecoveryAction))


if __name__ == "__main__":
    unittest.main()
