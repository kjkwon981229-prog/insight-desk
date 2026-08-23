from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, RenderMode
from insight_desk.generation import GeneratedDraft, GenerationContractError, GenerationRequest
from insight_desk.generation_pipeline import (
    FALLBACK_HEADLINE_MAX_CHARS,
    FALLBACK_SUMMARY_MAX_CHARS,
    GenerationAttemptKind,
    GenerationAttemptStatus,
    generate_with_recovery,
)


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def request(text: str = TEXT) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:recovery",
        article_id="article:recovery",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:recovery",
        subject="네오팩토리",
        action="AI 공장 구축 사업을 15억달러에 수주했다",
        object="AI 공장 구축 사업",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:recovery",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(event=event, facts={fact.fact_id: fact}, evidence={span.evidence_id: span})


@dataclass
class SequenceGenerator:
    outcomes: list[object] = field(default_factory=list)
    calls: int = 0

    def generate(self, item: GenerationRequest) -> GeneratedDraft:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, GeneratedDraft)
        return outcome


def valid_draft() -> GeneratedDraft:
    return GeneratedDraft(
        event_id="event:recovery",
        headline="AI 공장 15억달러 수주",
        summary="네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.",
        evidence_ids=("ev:recovery",),
    )


def invalid_draft() -> GeneratedDraft:
    return GeneratedDraft(
        event_id="event:recovery",
        headline="AI 공장 20억달러 수주",
        summary="네오팩토리가 AI 공장 구축 사업을 20억달러에 수주했다.",
        evidence_ids=("ev:recovery",),
    )


class Phase7GenerationRecoveryTests(unittest.TestCase):
    def test_primary_success_returns_generated_mode_without_extra_calls(self) -> None:
        primary = SequenceGenerator([valid_draft()])
        result = generate_with_recovery(request(), primary=primary)
        self.assertIs(result.render_mode, RenderMode.GENERATED)
        self.assertEqual(primary.calls, 1)
        self.assertEqual(len(result.attempts), 1)
        self.assertIs(result.attempts[0].status, GenerationAttemptStatus.ACCEPTED)

    def test_preservation_failure_retries_primary_once(self) -> None:
        primary = SequenceGenerator([invalid_draft(), valid_draft()])
        result = generate_with_recovery(request(), primary=primary)
        self.assertEqual(primary.calls, 2)
        self.assertEqual(
            [attempt.status for attempt in result.attempts],
            [GenerationAttemptStatus.PRESERVATION_REJECTED, GenerationAttemptStatus.ACCEPTED],
        )

    def test_explicit_alternate_is_used_only_after_two_primary_failures(self) -> None:
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        alternate = SequenceGenerator([valid_draft()])
        result = generate_with_recovery(request(), primary=primary, alternate=alternate)
        self.assertIs(result.render_mode, RenderMode.GENERATED)
        self.assertEqual(primary.calls, 2)
        self.assertEqual(alternate.calls, 1)
        self.assertEqual(result.attempts[-1].kind, GenerationAttemptKind.ALTERNATE)

    def test_no_configured_alternate_falls_back_to_exact_source(self) -> None:
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        result = generate_with_recovery(request(), primary=primary)
        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.draft.headline, TEXT)
        self.assertEqual(result.draft.summary, TEXT)
        self.assertEqual(result.draft.event_id, request().event.event_id)
        self.assertEqual(result.attempts[-1].kind, GenerationAttemptKind.EXTRACTIVE_FALLBACK)
        self.assertTrue(result.preservation.accepted)

    def test_live_106_char_complete_sentence_is_not_cut_at_legacy_96_limit(self) -> None:
        text = (
            "김경문 감독이 이끄는 한화 이글스는 23일 대전 한화생명볼파크에서 열린 2026 신한 SOL Bank KBO리그 "
            "LG 트윈스와 시즌 13차전에서 3-12로 대패하며 연승에 실패했다."
        )
        self.assertGreater(len(text), 96)
        self.assertLessEqual(len(text), 120)
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        result = generate_with_recovery(request(text), primary=primary)
        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.draft.headline, text)
        self.assertNotEqual(result.draft.headline[-3:], "연승에")

    def test_exact_fallback_never_raw_character_clips_without_safe_boundary(self) -> None:
        text = "네오팩토리가 " + ("초장문근거문장" * 24) + " 사업을 수주했다."
        self.assertGreater(len(text), 120)
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        with self.assertRaises(GenerationContractError):
            generate_with_recovery(request(text), primary=primary)

    def test_long_article_fallback_is_bounded_and_source_exact(self) -> None:
        title = "SK하이닉스 임단협 잠정합의안 찬반투표"
        paragraph = (
            "SK하이닉스 노사가 성과급인 초과이익분배금의 일부를 자사주로 지급하는 잠정합의안을 마련했다. "
            "조합원 투표는 24일부터 25일까지 진행된다. "
            "회사는 세부 지급 기준을 사내에 공지했다고 밝혔다."
        )
        long_text = title + "\n" + paragraph * 12
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        result = generate_with_recovery(request(long_text), primary=primary)
        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.draft.headline, title)
        self.assertLessEqual(len(result.draft.headline), FALLBACK_HEADLINE_MAX_CHARS)
        self.assertLessEqual(len(result.draft.summary), FALLBACK_SUMMARY_MAX_CHARS)
        self.assertIn(result.draft.headline, long_text)
        self.assertIn(result.draft.summary, long_text)
        self.assertNotEqual(result.draft.summary, long_text)
        self.assertTrue(result.preservation.accepted)

    def test_failed_alternate_still_preserves_event_via_fallback(self) -> None:
        primary = SequenceGenerator([RuntimeError("a"), RuntimeError("b")])
        alternate = SequenceGenerator([RuntimeError("c")])
        result = generate_with_recovery(request(), primary=primary, alternate=alternate)
        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertEqual(result.event_id, "event:recovery")
        self.assertEqual([a.kind for a in result.attempts], [
            GenerationAttemptKind.PRIMARY,
            GenerationAttemptKind.PRIMARY,
            GenerationAttemptKind.ALTERNATE,
            GenerationAttemptKind.EXTRACTIVE_FALLBACK,
        ])
        self.assertTrue(all(not hasattr(a, "global_abort") for a in result.attempts))


if __name__ == "__main__":
    unittest.main()
