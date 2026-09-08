from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, VerificationCheck
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.phase7 import VerificationRecoveryReason, produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
FALLBACK_HEADLINE = "AI 공장 구축 사업을 15억달러에 수주했다"


def request(text: str = TEXT) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:phase7-final",
        article_id="article:phase7-final",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:phase7-final",
        subject="네오팩토리",
        action=FALLBACK_HEADLINE,
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase7-final",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(event=event, facts={fact.fact_id: fact}, evidence={span.evidence_id: span})


def identity_sensitive_request() -> GenerationRequest:
    text = "전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다."
    span = EvidenceSpan(
        evidence_id="ev:phase7-identity-recovery",
        article_id="article:phase7-identity-recovery",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:phase7-identity-recovery",
        subject="PCE 물가",
        action="0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase7-identity-recovery",
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(event=event, facts={fact.fact_id: fact}, evidence={span.evidence_id: span})


@dataclass
class Generator:
    draft: GeneratedDraft | None = None
    error: Exception | None = None
    calls: int = 0

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.draft is not None
        return self.draft


@dataclass
class Verifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    calls: int = 0

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        self.calls += 1
        answer = self.answers.pop(0) if self.answers else True
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=answer,
            error_code=None if answer is not None else "synthetic_indeterminate",
            zero_cost=True,
        )


def generated() -> GeneratedDraft:
    return GeneratedDraft(
        event_id="event:phase7-final",
        headline="AI 공장 15억달러 수주",
        summary="네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.",
        evidence_ids=("ev:phase7-final",),
    )


def identity_sensitive_generated() -> GeneratedDraft:
    return GeneratedDraft(
        event_id="event:phase7-identity-recovery",
        headline="PCE 물가, 0.2% 올라 전월 하락에서 상승 전환",
        summary="전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다.",
        evidence_ids=("ev:phase7-identity-recovery",),
    )


def primary(*answers: bool | None) -> Verifier:
    return Verifier(CLOUDFLARE_VERIFIER_ID, "@cf/meta/llama-3.3-70b-instruct-fp8-fast", list(answers))


def secondary(*answers: bool | None) -> Verifier:
    return Verifier(LOCAL_NLI_VERIFIER_ID, "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", list(answers))


class Phase7PublishGateTests(unittest.TestCase):
    def test_supported_generated_candidate_is_publishable_without_fallback(self) -> None:
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=Generator(draft=generated()),
            primary_verifier=primary(True, True),
            secondary_verifier=secondary(True, True),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.publishable)
        self.assertIs(result.initial_generation, result.final_generation)
        self.assertIsNone(result.verification_recovery_reason)
        self.assertTrue(result.event_retained)

    def test_explicit_generated_claim_rejection_does_not_fail_over_to_different_text(self) -> None:
        first = primary(False, False)
        second = secondary(True, True)
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=Generator(draft=generated()),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result.publishable)
        self.assertIs(result.initial_generation, result.final_generation)
        self.assertIsNone(result.verification_recovery_reason)
        self.assertEqual(first.calls, 2)
        self.assertEqual(second.calls, 0)
        self.assertTrue(result.event_retained)

    def test_indeterminate_verification_recovers_to_exact_source(self) -> None:
        first = primary(None, None)
        second = secondary(True, True)
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=Generator(draft=generated()),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.publishable)
        self.assertEqual(result.final_generation.draft.headline, FALLBACK_HEADLINE)
        self.assertEqual(result.final_generation.draft.summary, TEXT)
        self.assertIn(result.final_generation.draft.headline, TEXT)
        self.assertIs(
            result.verification_recovery_reason,
            VerificationRecoveryReason.GENERATED_VERIFICATION_UNAVAILABLE,
        )
        self.assertEqual(first.calls, 2)
        self.assertEqual(second.calls, 0)
        self.assertTrue(result.event_retained)

    def test_identity_preserving_indeterminate_fallback_recovers_to_exact_source(self) -> None:
        first = primary(None, None)
        second = secondary(True, True)
        result = produce_phase7_entry_candidate(
            identity_sensitive_request(),
            primary_generator=Generator(draft=identity_sensitive_generated()),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.publishable)
        self.assertEqual(
            result.final_generation.draft.headline,
            "PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다",
        )
        self.assertEqual(
            result.final_generation.draft.summary,
            "전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다.",
        )
        self.assertIs(
            result.verification_recovery_reason,
            VerificationRecoveryReason.GENERATED_VERIFICATION_UNAVAILABLE,
        )
        self.assertEqual(first.calls, 2)
        self.assertEqual(second.calls, 0)
        self.assertTrue(result.event_retained)

    def test_unsafe_indeterminate_exact_fallback_fails_closed_item_locally(self) -> None:
        long_text = (
            "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다 "
            + ("초장문근거문장" * 24)
        )
        self.assertGreater(len(long_text), 120)
        first = primary(None, None)
        second = secondary(True, True)
        result = produce_phase7_entry_candidate(
            request(long_text),
            primary_generator=Generator(draft=generated()),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result.publishable)
        self.assertIs(result.initial_generation, result.final_generation)
        self.assertIsNone(result.verification_recovery_reason)
        self.assertTrue(result.event_retained)

    def test_generation_failure_with_unsafe_exact_source_returns_no_item_candidate(self) -> None:
        long_text = "네오팩토리가 " + ("초장문근거문장" * 24) + " 사업을 수주했다."
        first = primary(False, False)
        second = secondary(False, False)
        result = produce_phase7_entry_candidate(
            request(long_text),
            primary_generator=Generator(error=RuntimeError("down")),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNone(result)
        self.assertEqual(first.calls, 0)
        self.assertEqual(second.calls, 0)

    def test_generation_failure_path_finishes_in_exact_fallback_without_external_verifiers(self) -> None:
        first = primary(False, False)
        second = secondary(False, False)
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=Generator(error=RuntimeError("down")),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.publishable)
        self.assertEqual(result.final_generation.draft.headline, FALLBACK_HEADLINE)
        self.assertEqual(result.final_generation.draft.summary, TEXT)
        self.assertIn(result.final_generation.draft.headline, TEXT)
        self.assertEqual(first.calls, 0)
        self.assertEqual(second.calls, 0)
        self.assertIsNone(result.verification_recovery_reason)
        self.assertTrue(result.event_retained)

    def test_explicit_generated_rejection_remains_rejected_even_if_secondary_is_unavailable(self) -> None:
        first = primary(False, False)
        second = secondary(None, None)
        result = produce_phase7_entry_candidate(
            request(),
            primary_generator=Generator(draft=generated()),
            primary_verifier=first,
            secondary_verifier=second,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result.publishable)
        self.assertIs(result.initial_generation, result.final_generation)
        self.assertEqual(first.calls, 2)
        self.assertEqual(second.calls, 0)
        self.assertTrue(result.event_retained)


if __name__ == "__main__":
    unittest.main()
