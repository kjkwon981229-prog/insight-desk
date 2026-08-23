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
    MAX_FEED_HEADLINE_CHARS,
    MAX_FEED_SUMMARY_CHARS,
    RenderingContractError,
    build_rendered_briefing,
    feed_text_fits,
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
    headline: str = "AI 공장 15억달러 수주"
    summary: str = TEXT

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        if self.fail:
            raise RuntimeError("synthetic generation failure")
        return GeneratedDraft(
            event_id=item.event.event_id,
            headline=self.headline,
            summary=self.summary,
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


@dataclass(frozen=True)
class UnpublishableCandidate:
    event_id: str
    publishable: bool = False


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
    headline: str = "AI 공장 15억달러 수주",
    summary: str = TEXT,
    primary_answers: tuple[bool | None, ...] = (True, True),
    secondary_answers: tuple[bool | None, ...] = (True, True),
) -> Phase7EntryCandidate:
    return produce_phase7_entry_candidate(
        request(event_id),
        primary_generator=Generator(
            event_id=event_id,
            fail=generated_fail,
            headline=headline,
            summary=summary,
        ),
        primary_verifier=primary(*primary_answers),
        secondary_verifier=secondary(*secondary_answers),
    )


def verified_variant(event_id: str, *, headline: str, summary: str) -> Phase7EntryCandidate:
    """Build a renderer fixture that is already verified upstream, without rerunning preservation."""

    base = candidate(event_id)
    draft = replace(base.final_generation.draft, headline=headline, summary=summary)
    generation = replace(base.final_generation, draft=draft)
    claim_results = []
    for item in base.verification.claims:
        text = headline if item.role.value == "headline" else summary
        claim_results.append(replace(item, claim=replace(item.claim, text=text)))
    verification = replace(base.verification, claims=tuple(claim_results))
    return replace(
        base,
        initial_generation=generation,
        final_generation=generation,
        verification=verification,
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
        rejected = UnpublishableCandidate("event:phase8")
        accepted = candidate("event:phase8-good")
        self.assertIsNone(render_phase7_candidate(rejected))  # type: ignore[arg-type]
        briefing = build_rendered_briefing(
            briefing_id="briefing:phase8",
            generated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            candidates=(rejected, accepted),  # type: ignore[arg-type]
        )
        self.assertEqual([entry.event_id for entry in briefing.entries], ["event:phase8-good"])

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

    def test_feed_size_gate_omits_oversized_verified_text_item_locally(self) -> None:
        self.assertFalse(
            feed_text_fits(
                headline="가" * (MAX_FEED_HEADLINE_CHARS + 1),
                summary="나" * 10,
            )
        )
        self.assertFalse(
            feed_text_fits(
                headline="가" * 10,
                summary="나" * (MAX_FEED_SUMMARY_CHARS + 1),
            )
        )

    def test_duplicate_content_from_distinct_events_renders_once(self) -> None:
        first = candidate("event:phase8-a")
        second = candidate("event:phase8-b")
        briefing = build_rendered_briefing(
            briefing_id="briefing:content-dedup",
            generated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            candidates=(first, second),
        )
        self.assertEqual([entry.event_id for entry in briefing.entries], ["event:phase8-a"])

    def test_same_normalized_headline_with_variant_summaries_renders_once(self) -> None:
        first = verified_variant(
            "event:rate-a",
            headline="27일 한국은행 기준금리 결정 주목",
            summary="오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠리고 있습니다.",
        )
        second = verified_variant(
            "event:rate-b",
            headline=" 27일   한국은행 기준금리 결정 주목 ",
            summary="오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠립니다.",
        )
        briefing = build_rendered_briefing(
            briefing_id="briefing:headline-dedup",
            generated_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
            candidates=(first, second),
        )
        self.assertEqual([entry.event_id for entry in briefing.entries], ["event:rate-a"])

    def test_same_normalized_summary_with_distinct_headlines_renders_once(self) -> None:
        summary = "오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠립니다."
        first = verified_variant(
            "event:rate-summary-a",
            headline="27일 한국은행 기준금리 결정에 이목 집중",
            summary=summary,
        )
        second = verified_variant(
            "event:rate-summary-b",
            headline="27일 한국은행 기준금리 결정에 관심",
            summary=" 오는 27일  예정된 한국은행의 기준금리 결정에 관심이 쏠립니다. ",
        )
        briefing = build_rendered_briefing(
            briefing_id="briefing:summary-dedup",
            generated_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
            candidates=(first, second),
        )
        self.assertEqual([entry.event_id for entry in briefing.entries], ["event:rate-summary-a"])

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
