from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.semantic.events import compare_candidate_identity
from insight_desk.semantic.market_identity import same_market_session_fact_perspective
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 17, 10, tzinfo=timezone.utc)


class Live313VisibleStoryRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_interpretive_background_expression_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="AI 개발에서 막대한 컴퓨팅 능력 확보 중요성 강조",
            summary=(
                "AI 개발에서 막대한 컴퓨팅 능력을 확보하는 것이 중요하다는 오픈AI의 "
                "기술 문화를 상징적으로 드러낸 표현이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_actual_chip_benchmark_event_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="오픈AI, Jalapeño 추론 칩 벤치마크 공개",
            summary=(
                "오픈AI는 25일 Jalapeño의 InferenceX 벤치마크 결과를 공개하고 "
                "DeepSeek R1에서 엔비디아 GB300보다 높은 전력당 처리량을 기록했다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_orphaned_test_and_chip_references_are_not_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="리처드 호, 엔비디아 GB300과 반도체 성능 비교",
            summary=(
                "리처드 호는 인터뷰에서 해당 테스트에 사용된 공개 벤치마킹 시스템에서 "
                "엔비디아의 GB300과 이 반도체를 비교 측정했다고 밝혔다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_chip_reference_remains_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="리처드 호, Jalapeño와 엔비디아 GB300 성능 비교",
            summary=(
                "오픈AI 하드웨어 책임자 리처드 호는 공개 InferenceX 테스트에서 "
                "Jalapeño와 엔비디아 GB300을 비교 측정했다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_generic_hanwha_game_loss_without_opponent_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="한화 이글스, 불펜진 난조로 경기 패배",
            summary="프로야구 한화 이글스가 불펜진의 붕괴로 인해 경기를 내주었다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_identified_hanwha_game_result_remains_accepted(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="한화, 25일 SSG전 1-7 패배",
            summary=(
                "한화 이글스는 25일 인천 SSG랜더스필드에서 열린 SSG 랜더스와의 경기에서 "
                "1-7로 패했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live313MarketIdentityRegressions(unittest.TestCase):
    LEFT_TEXT = (
        "25일 하락 출발한 코스피 지수가 장중 낙폭을 모두 만회하고 상승 마감했다. "
        "코스피 지수는 전 거래일보다 45.78포인트(0.68%) 오른 6742.74에 거래를 마쳤다."
    )
    RIGHT_TEXT = (
        "25일 하락 출발한 국내 증시는 개인과 기관의 매수세가 유입되면서 "
        "장중 낙폭을 회복하고 상승세로 장을 마쳤다."
    )

    def test_broad_market_identity_can_use_full_fact_surface_not_only_subject(self) -> None:
        self.assertTrue(
            same_market_session_fact_perspective(
                left_subject="코스피 지수",
                right_subject="개인·기관 매수세",
                left_text=self.LEFT_TEXT,
                right_text=self.RIGHT_TEXT,
                left_date="25일",
                right_date="2026년 8월 25일",
            )
        )

    def test_same_session_evidence_reaches_semantic_identity_despite_surface_subject_date_forms(self) -> None:
        left = CandidateEvent("left", "economy", ("lf",), ("la",))
        right = CandidateEvent("right", "economy", ("rf",), ("ra",))
        facts = {
            "lf": EventFact(
                fact_id="lf",
                subject="코스피 지수",
                action="6742.74에 거래를 마쳤다",
                evidence_ids=("le",),
                event_date="25일",
            ),
            "rf": EventFact(
                fact_id="rf",
                subject="개인·기관 매수세",
                action="국내 증시가 상승세로 장을 마쳤다",
                evidence_ids=("re",),
                event_date="2026년 8월 25일",
            ),
        }
        decision = compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=True,
            left_evidence_text=self.LEFT_TEXT,
            right_evidence_text=self.RIGHT_TEXT,
        )
        self.assertTrue(decision.same_event, decision.reason)
        self.assertFalse(decision.deterministic_block)

    def test_different_session_remains_blocked(self) -> None:
        left = CandidateEvent("left", "economy", ("lf",), ("la",))
        right = CandidateEvent("right", "economy", ("rf",), ("ra",))
        facts = {
            "lf": EventFact("lf", "코스피 지수", "상승 마감", ("le",), event_date="25일"),
            "rf": EventFact("rf", "국내 증시", "상승 마감", ("re",), event_date="24일"),
        }
        decision = compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=True,
            left_evidence_text=self.LEFT_TEXT,
            right_evidence_text=self.RIGHT_TEXT.replace("25일", "24일", 1),
        )
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)

    def test_production_wires_identity_evidence_into_both_identity_decisions(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("left_evidence_text=identity_text"), 2)
        self.assertGreaterEqual(source.count("right_evidence_text=prior.identity_text"), 2)


if __name__ == "__main__":
    unittest.main()
