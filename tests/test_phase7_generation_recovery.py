from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, RenderMode
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.generation_pipeline import (
    GenerationAttemptKind,
    GenerationAttemptStatus,
    generate_with_recovery,
)


TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def request() -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:recovery",
        article_id="article:recovery",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
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
