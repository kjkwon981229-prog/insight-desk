from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    VerificationCheck,
    VerificationVerdict,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.verification_pipeline import ClaimRole, verify_generated_draft


TEXT_A = "한국은행 부총재는 물가 흐름을 더 지켜봐야 한다고 밝혔다."
TEXT_B = "원·달러 환율은 1386.5원으로 마감했다."


def request() -> GenerationRequest:
    first = EvidenceSpan(
        evidence_id="ev:a",
        article_id="article:phase7",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT_A),
        text=TEXT_A,
    )
    second = EvidenceSpan(
        evidence_id="ev:b",
        article_id="article:phase7",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT_B),
        text=TEXT_B,
    )
    fact_a = EventFact(
        fact_id="fact:a",
        subject="한국은행 부총재",
        action="물가 흐름을 더 지켜봐야 한다고 밝혔다",
        evidence_ids=(first.evidence_id,),
    )
    fact_b = EventFact(
        fact_id="fact:b",
        subject="원·달러 환율",
        action="1386.5원으로 마감했다",
        evidence_ids=(second.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase7-verify",
        topic_id="economy",
        fact_ids=(fact_a.fact_id, fact_b.fact_id),
        article_ids=(first.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact_a.fact_id: fact_a, fact_b.fact_id: fact_b},
        evidence={first.evidence_id: first, second.evidence_id: second},
    )


@dataclass
class FakeVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    raise_error: bool = False
    calls: list[tuple[str, str, tuple[str, ...]]] = field(default_factory=list)

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        self.calls.append((claim_text, evidence_text, evidence_ids))
        if self.raise_error:
            raise RuntimeError("synthetic verifier failure")
        entailed = self.answers.pop(0) if self.answers else True
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=entailed,
            error_code=None if entailed is not None else "synthetic_inconclusive",
            zero_cost=True,
        )


def primary(*answers: bool | None, raise_error: bool = False) -> FakeVerifier:
    return FakeVerifier(
        verifier_id=CLOUDFLARE_VERIFIER_ID,
        model_id="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        answers=list(answers),
        raise_error=raise_error,
    )


def secondary(*answers: bool | None) -> FakeVerifier:
    return FakeVerifier(
        verifier_id=LOCAL_NLI_VERIFIER_ID,
        model_id="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        answers=list(answers),
    )


class Phase7ClaimVerificationTests(unittest.TestCase):
    def test_preservation_failure_stops_before_both_verifiers(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="환율 1399.9원 마감",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        first = primary(True, True)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertFalse(result.preservation.accepted)
        self.assertEqual(result.claims, ())
        self.assertFalse(result.publishable)
        self.assertEqual(first.calls, [])
        self.assertEqual(second.calls, [])

    def test_primary_false_is_final_rejection_without_secondary_compute(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="한국은행 물가 흐름 관찰",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        first = primary(False, False)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertEqual(len(result.claims), 2)
        self.assertTrue(all(x.claim.verdict is VerificationVerdict.REJECTED for x in result.claims))
        self.assertFalse(result.publishable)
        self.assertEqual(len(first.calls), 2)
        self.assertEqual(second.calls, [])

    def test_primary_and_secondary_true_support_both_claims(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="환율 1386.5원 마감",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        first = primary(True, True)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertEqual([x.role for x in result.claims], [ClaimRole.HEADLINE, ClaimRole.SUMMARY])
        self.assertTrue(all(x.claim.verdict is VerificationVerdict.SUPPORTED for x in result.claims))
        self.assertTrue(result.publishable)
        self.assertEqual(len(first.calls), 2)
        self.assertEqual(len(second.calls), 2)

    def test_secondary_false_after_primary_true_is_indeterminate(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="한국은행 물가 흐름 관찰",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        result = verify_generated_draft(
            item,
            draft,
            primary=primary(True, True),
            secondary=secondary(False, True),
        )
        self.assertIs(result.claims[0].claim.verdict, VerificationVerdict.INDETERMINATE)
        self.assertIs(result.claims[1].claim.verdict, VerificationVerdict.SUPPORTED)
        self.assertFalse(result.publishable)

    def test_primary_exception_becomes_item_local_indeterminate(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="한국은행 물가 흐름 관찰",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        first = primary(raise_error=True)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertTrue(all(x.claim.verdict is VerificationVerdict.INDETERMINATE for x in result.claims))
        self.assertFalse(result.publishable)
        self.assertEqual(second.calls, [])
        for generated in result.claims:
            self.assertIsNone(generated.claim.checks[0].entailed)
            self.assertIn("verifier_exception:runtimeerror", generated.claim.checks[0].error_code or "")

    def test_only_draft_cited_evidence_can_support_preservation_and_verification(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="환율 1386.5원 마감",
            summary="환율 마감 소식",
            evidence_ids=("ev:a",),
        )
        first = primary(True, True)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertFalse(result.preservation.accepted)
        self.assertEqual(result.claims, ())
        self.assertEqual(first.calls, [])
        self.assertEqual(second.calls, [])

    def test_verifiers_receive_only_draft_cited_evidence_subset(self) -> None:
        item = request()
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="한국은행 물가 흐름 관찰",
            summary="한국은행 부총재가 물가 흐름을 더 지켜본다고 밝혔다.",
            evidence_ids=("ev:a",),
        )
        first = primary(True, True)
        second = secondary(True, True)
        result = verify_generated_draft(item, draft, primary=first, secondary=second)
        self.assertTrue(result.publishable)
        self.assertTrue(first.calls)
        self.assertTrue(secondary)
        for _, evidence_text, evidence_ids in first.calls + second.calls:
            self.assertEqual(evidence_text, TEXT_A)
            self.assertEqual(evidence_ids, ("ev:a",))


if __name__ == "__main__":
    unittest.main()
