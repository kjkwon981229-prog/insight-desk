from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RenderMode,
    VerificationCheck,
)
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.phase7 import Phase7EntryCandidate, produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from insight_desk.rendering import (
    RenderingContractError,
    build_rendered_briefing,
    render_phase7_candidate,
)


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def request(event_id: str = "event:phase8") -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id=f"ev:{event_id}",
        article_id=f"article:{event_id}",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
    )
    fact = EventFact(
        fact_id=f"fact:{event_id}",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


@dataclass
class Generator:
    event_id: str = "event:phase8"
    fail: bool = False

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        if self.fail:
            raise RuntimeError("synthetic generation failure")
        return GeneratedDraft(
            event_id=item.event.event_id,
            headline="AI 공장 15억달러 수주",
            summary=TEXT,
            evidence_ids=item.evidence_ids,
        )


@dataclass
class Verifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
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


def primary(*answers: bool | None) -> Verifier:
    return Verifier(
        CLOUDFLARE_VERIFIER_ID,
        "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        list(answers),
    )


def secondary(*answers: bool | None) -> Verifier:
    return Verifier(
        LOCAL_NLI_VERIFIER_ID,
        "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        list(answers),
    )


def candidate(
    event_id: str = "event:phase8",
    *,
    generated_fail: bool = False,
    primary_answers: tuple[bool | None, ...] = (True, True),
    secondary_answers: tuple[bool | None, ...] = (True, True),
) -> Phase7EntryCandidate:
    return produce_phase7_entry_candidate(
        request(event_id),
        primary_generator=Generator(event_id=event_id, fail=generated_fail),
        primary_verifier=primary(*primary_answers),
        secondary_verifier=secondary(*secondary_answers),
    )


class Phase8RenderingBridgeTests(unittest.TestCase):
    def test_supported_candidate_renders_only_verified_contract_fields(self) -> None:
        item = candidate()
        entry = render_phase7_candidate(item)
        assert entry is not None
        self.assertEqual(entry.event_id, item.event_id)
        self.assertEqual(entry.headline, item.final_generation.draft.headline)
        self.assertEqual(entry.summary, item.final_generation.draft.summary)
        self.assertEqual(len(entry.claim_ids), 2)
        self.assertIs(entry.render_mode, RenderMode.GENERATED)

    def test_unpublishable_candidate_is_omitted_item_locally(self) -> None:
        rejected = candidate(primary_answers=(None, None), secondary_answers=(True, True))
        accepted = candidate("event:phase8-good")
        briefing = build_rendered_briefing(
            briefing_id="briefing:phase8",
            generated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            candidates=(rejected, accepted),
        )
        self.assertEqual([entry.event_id for entry in briefing.entries], ["event:phase8-good"])
        self.assertTrue(rejected.event_retained)

    def test_verified_text_mismatch_is_rejected_instead_of_rendered(self) -> None:
        item = candidate()
        headline_result = item.verification.claims[0]
        mutated_claim = replace(headline_result.claim, text="검증되지 않은 다른 제목")
        mutated_result = replace(headline_result, claim=mutated_claim)
        mutated_verification = replace(
            item.verification,
            claims=(mutated_result, item.verification.claims[1]),
        )
        mutated_candidate = replace(item, verification=mutated_verification)
        with self.assertRaises(RenderingContractError):
            render_phase7_candidate(mutated_candidate)

    def test_extractive_fallback_mode_survives_renderer_bridge(self) -> None:
        item = candidate(generated_fail=True)
        entry = render_phase7_candidate(item)
        assert entry is not None
        self.assertIs(entry.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(entry.headline, TEXT)
        self.assertEqual(entry.summary, TEXT)

    def test_duplicate_rendered_event_ids_fail_closed(self) -> None:
        item = candidate()
        with self.assertRaises(RenderingContractError):
            build_rendered_briefing(
                briefing_id="briefing:duplicate",
                generated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
                candidates=(item, item),
            )


if __name__ == "__main__":
    unittest.main()
