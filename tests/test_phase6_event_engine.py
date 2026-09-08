from __future__ import annotations

import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    SelectionSignals,
    SelectionVerdict,
    TemporalState,
)
from insight_desk.semantic import (
    Phase6EventEngine,
    TemporalResolutionSource,
    compare_candidate_identity,
    detect_explicit_temporal_state,
    resolve_temporal_state,
)


def span(evidence_id: str, article_id: str, text: str) -> EvidenceSpan:
    return EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )


def signals(*, identity_resolved: bool = True, material_event: bool | None = True) -> SelectionSignals:
    return SelectionSignals(
        topic_relevant=True,
        material_event=material_event,
        fresh=True,
        source_usable=True,
        identity_resolved=identity_resolved,
    )


class FakeTemporalAuxiliary:
    def __init__(self, result: TemporalState = TemporalState.RESUMED, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def classify_temporal(self, text: str) -> TemporalState:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.result


class Phase6TemporalTests(unittest.TestCase):
    def test_explicit_resume_future_is_deterministic_and_skips_auxiliary(self) -> None:
        evidence = span(
            "ev1",
            "a1",
            "프로야구가 폭염 때문에 5일 동안 중단됐다가 오늘 재개한다.",
        )
        fact = EventFact("f1", "프로야구", "경기 재개", ("ev1",))
        event = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        auxiliary = FakeTemporalAuxiliary(TemporalState.ANNOUNCED_PROSPECTIVE)

        result = resolve_temporal_state(event, fact, {"ev1": evidence}, auxiliary=auxiliary)
        self.assertIs(result.state, TemporalState.RESUMING)
        self.assertIs(result.source, TemporalResolutionSource.DETERMINISTIC)
        self.assertFalse(result.auxiliary_used)
        self.assertEqual(auxiliary.calls, [])

    def test_explicit_cancel_and_completed_cues_are_high_precision(self) -> None:
        self.assertIs(
            detect_explicit_temporal_state("서울 경기가 폭염 영향으로 취소됐다."),
            TemporalState.CANCELLED,
        )
        self.assertIs(
            detect_explicit_temporal_state("프로젝트 구축을 완료했다."),
            TemporalState.COMPLETED,
        )
        self.assertIs(
            detect_explicit_temporal_state("현재 공사가 진행 중이다."),
            TemporalState.ONGOING,
        )

    def test_multiple_different_explicit_states_are_not_guessed(self) -> None:
        self.assertIsNone(
            detect_explicit_temporal_state("다음 주 재개한다고 밝혔으나 결국 경기를 취소했다.")
        )

    def test_extracted_temporal_state_is_preserved_without_auxiliary_call(self) -> None:
        evidence = span("ev1", "a1", "KBO는 11일 경기를 재개했다.")
        fact = EventFact(
            fact_id="f1",
            subject="KBO",
            action="경기 재개",
            evidence_ids=("ev1",),
            temporal_state=TemporalState.RESUMED,
            event_date="2026-08-11",
        )
        event = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        auxiliary = FakeTemporalAuxiliary(TemporalState.PLANNED)

        result = resolve_temporal_state(event, fact, {"ev1": evidence}, auxiliary=auxiliary)
        self.assertIs(result.state, TemporalState.RESUMED)
        self.assertIs(result.source, TemporalResolutionSource.EXTRACTED)
        self.assertFalse(result.auxiliary_used)
        self.assertEqual(auxiliary.calls, [])

    def test_explicit_evidence_conflict_with_extracted_state_fails_closed(self) -> None:
        evidence = span("ev1", "a1", "KBO는 11일 경기를 재개했다.")
        fact = EventFact(
            "f1",
            "KBO",
            "경기 재개",
            ("ev1",),
            temporal_state=TemporalState.RESUMING,
        )
        event = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        auxiliary = FakeTemporalAuxiliary(TemporalState.RESUMED)

        result = resolve_temporal_state(event, fact, {"ev1": evidence}, auxiliary=auxiliary)
        self.assertIsNone(result.state)
        self.assertIs(result.source, TemporalResolutionSource.UNRESOLVED)
        self.assertFalse(result.auxiliary_used)
        self.assertIn("temporal_evidence_conflict", result.error_code or "")
        self.assertEqual(auxiliary.calls, [])

    def test_genuinely_unresolved_temporal_state_uses_only_bound_evidence(self) -> None:
        first = span("ev1", "a1", "정부는 다음 달 정책 시행 일정을 공식 발표했다.")
        unrelated = span("ev2", "a1", "다른 회사는 현재 공사를 진행 중이다.")
        fact = EventFact(
            fact_id="f1",
            subject="정부",
            action="정책 시행 일정 발표",
            evidence_ids=("ev1",),
            event_date="다음 달",
        )
        event = CandidateEvent("e1", "economy", ("f1",), ("a1",))
        auxiliary = FakeTemporalAuxiliary(TemporalState.ANNOUNCED_PROSPECTIVE)

        result = resolve_temporal_state(
            event,
            fact,
            {"ev1": first, "ev2": unrelated},
            auxiliary=auxiliary,
        )
        self.assertIs(result.state, TemporalState.ANNOUNCED_PROSPECTIVE)
        self.assertIs(result.source, TemporalResolutionSource.AUXILIARY)
        self.assertTrue(result.auxiliary_used)
        self.assertEqual(auxiliary.calls, [first.text])
        self.assertNotIn(unrelated.text, auxiliary.calls[0])

    def test_temporal_auxiliary_failure_is_item_local_and_unresolved(self) -> None:
        evidence = span("ev1", "a1", "경기 재개 여부는 아직 확정되지 않았다.")
        fact = EventFact("f1", "KBO", "경기 재개", ("ev1",))
        event = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        auxiliary = FakeTemporalAuxiliary(error=RuntimeError("provider down"))

        result = resolve_temporal_state(event, fact, {"ev1": evidence}, auxiliary=auxiliary)
        self.assertIsNone(result.state)
        self.assertIs(result.source, TemporalResolutionSource.UNRESOLVED)
        self.assertTrue(result.auxiliary_used)
        self.assertEqual(result.error_code, "temporal_auxiliary_error:RuntimeError")

    def test_temporal_auxiliary_contract_violation_fails_closed(self) -> None:
        evidence = span("ev1", "a1", "다음 주 경기 일정 변경 여부를 논의한다.")
        fact = EventFact("f1", "KBO", "일정 변경 논의", ("ev1",))
        event = CandidateEvent("e1", "sports", ("f1",), ("a1",))

        class BadAuxiliary:
            def classify_temporal(self, text):
                return "resumed"

        result = resolve_temporal_state(event, fact, {"ev1": evidence}, auxiliary=BadAuxiliary())
        self.assertIsNone(result.state)
        self.assertEqual(result.error_code, "temporal_auxiliary_contract_violation")


class Phase6IdentityTests(unittest.TestCase):
    def test_explicit_date_conflict_blocks_merge_even_if_semantic_judgment_says_same(self) -> None:
        left_fact = EventFact(
            "f1",
            "한화-두산",
            "경기 취소",
            ("ev1",),
            event_date="2026-08-12",
            location="서울",
            cause="폭염",
        )
        right_fact = EventFact(
            "f2",
            "한화-두산",
            "경기 취소",
            ("ev2",),
            event_date="2026-08-13",
            location="서울",
            cause="폭염",
        )
        left = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        right = CandidateEvent("e2", "sports", ("f2",), ("a2",))

        decision = compare_candidate_identity(
            left,
            right,
            {"f1": left_fact, "f2": right_fact},
            semantic_same_event=True,
        )
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)
        self.assertIn("event_date", decision.reason)

    def test_ambiguous_identity_without_semantic_judgment_stays_separate(self) -> None:
        left_fact = EventFact("f1", "KBO", "경기 재개", ("ev1",), event_date="2026-08-11")
        right_fact = EventFact("f2", "KBO", "경기 재개", ("ev2",), event_date="2026-08-11")
        left = CandidateEvent("e1", "sports", ("f1",), ("a1",))
        right = CandidateEvent("e2", "sports", ("f2",), ("a2",))

        decision = compare_candidate_identity(left, right, {"f1": left_fact, "f2": right_fact})
        self.assertFalse(decision.same_event)
        self.assertFalse(decision.deterministic_block)
        self.assertFalse(decision.llm_judgment_used)

    def test_cross_topic_candidates_are_blocked_before_semantic_judgment(self) -> None:
        left_fact = EventFact("f1", "정부", "발표", ("ev1",))
        right_fact = EventFact("f2", "정부", "발표", ("ev2",))
        left = CandidateEvent("e1", "economy", ("f1",), ("a1",))
        right = CandidateEvent("e2", "ai_tech", ("f2",), ("a2",))

        decision = compare_candidate_identity(
            left,
            right,
            {"f1": left_fact, "f2": right_fact},
            semantic_same_event=True,
        )
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)
        self.assertEqual(decision.reason, "topic_identity_conflict")


class Phase6EventAssessmentTests(unittest.TestCase):
    def test_assessment_connects_fact_identity_temporal_and_phase6_selection(self) -> None:
        evidence = span("ev1", "a1", "정부는 AI 규제안을 9월 3일부터 시행할 예정이라고 밝혔다.")
        fact = EventFact(
            fact_id="f1",
            subject="  정부  ",
            action="시행 예정 발표",
            object="AI 규제안",
            evidence_ids=("ev1",),
            temporal_state=TemporalState.ANNOUNCED_PROSPECTIVE,
            event_date="9월 3일",
            participants=("정부",),
        )
        event = CandidateEvent("e1", "ai_tech", ("f1",), ("a1",))

        result = Phase6EventEngine().assess(
            event,
            facts={"f1": fact},
            evidence={"ev1": evidence},
            selection_signals=signals(),
        )
        self.assertEqual(result.identity_keys[0].subject_key, "정부")
        self.assertEqual(result.identity_keys[0].object_key, "ai 규제안")
        self.assertIs(result.temporal[0].state, TemporalState.ANNOUNCED_PROSPECTIVE)
        self.assertIs(result.selection.verdict, SelectionVerdict.INCLUDE)

    def test_selection_defer_is_not_converted_into_non_event(self) -> None:
        evidence = span("ev1", "a1", "정부가 정책 검토에 착수했다.")
        fact = EventFact("f1", "정부", "정책 검토 착수", ("ev1",))
        event = CandidateEvent("e1", "economy", ("f1",), ("a1",))

        result = Phase6EventEngine().assess(
            event,
            facts={"f1": fact},
            evidence={"ev1": evidence},
            selection_signals=signals(material_event=None),
        )
        self.assertIs(result.selection.verdict, SelectionVerdict.DEFER)
        self.assertEqual(result.event, event)

    def test_missing_fact_is_rejected_as_contract_input_error(self) -> None:
        event = CandidateEvent("e1", "economy", ("f-missing",), ("a1",))
        with self.assertRaisesRegex(ValueError, "missing fact"):
            Phase6EventEngine().assess(
                event,
                facts={},
                evidence={},
                selection_signals=signals(),
            )


if __name__ == "__main__":
    unittest.main()
