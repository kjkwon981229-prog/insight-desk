from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.semantic.statistical_identity import same_statistical_release_fingerprint
from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 4, 20, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live343ConditionalBenefitRegressions(unittest.TestCase):
    def test_live_conditional_investment_benefit_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="비수도권 첨단산업 투자, 일자리·경제 활성화 기대",
            summary=(
                "비수도권에 반도체와 AI 데이터센터 등 전력 다소비 첨단산업을 "
                "투자하면 지역 일자리 창출과 경제 활성화에 도움이 될 것으로 기대됐다"
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_policy_event_may_carry_a_later_expected_benefit(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="정부, 26일 지역별 차등 전기요금제 시행 발표",
            summary=(
                "정부는 26일 지역별 차등 전기요금제를 시행한다고 발표했다. "
                "비수도권 첨단산업 투자를 유도할 것으로 기대된다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live343RollingSportsBackgroundRegressions(unittest.TestCase):
    def test_live_rolling_team_form_record_alone_is_not_an_event(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 이글스 10경기 2승 8패 기록",
            summary="한화 이글스는 최근 10경기에서 2승 8패를 기록했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_game_result_is_not_erased_by_rolling_form_background(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화, 26일 KIA전 5-3 승리",
            summary=(
                "한화는 26일 KIA를 5-3으로 꺾고 6연패에서 탈출했다. "
                "최근 10경기 성적은 3승 7패다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live343SourceBackedStatisticalReleaseIdentityRegressions(unittest.TestCase):
    PRIOR_HEADLINE = "김성준·고정금리 높아 소비자 선택"
    PRIOR_SUMMARY = (
        "김성준 한국은행 금융통계팀장이 변동금리보다 고정금리가 더 높아 "
        "소비자들이 낮은 금리를 선택하는 경향이 있다고 설명했다."
    )
    CANDIDATE_HEADLINE = "가계대출 금리 4.64%로 전월 대비 0.14%포인트 상승"
    CANDIDATE_SUMMARY = (
        "한국은행이 26일 발표한 ‘2026년 7월 금융기관 가중평균금리’ 통계에 따르면 "
        "7월 예금은행의 가계대출 금리가 연 4.64%로, 한 달 전 대비 "
        "0.14%포인트(p) 올랐다."
    )
    PRIOR_SOURCE = (
        "한국은행이 26일 발표한 ‘2026년 7월 금융기관 가중평균 금리’ 통계에 따르면 "
        "7월 주택담보대출 중 고정형 금리 비중은 31.9%로 낮아졌다. "
        "김성준 한국은행 금융통계팀장은 변동금리보다 고정금리가 높아 소비자가 "
        "낮은 금리를 선택하는 유인이 크다고 설명했다."
    )
    CANDIDATE_SOURCE = (
        "한국은행이 26일 발표한 ‘2026년 7월 금융기관 가중평균 금리’ 통계에 따르면 "
        "7월 예금은행 가계대출 금리는 연 4.64%로 전월보다 0.14%포인트 올랐다."
    )

    def test_live_same_release_survives_generated_surface_information_loss(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="economy",
                prior_headline=self.PRIOR_HEADLINE,
                prior_summary=self.PRIOR_SUMMARY,
                candidate_headline=self.CANDIDATE_HEADLINE,
                candidate_summary=self.CANDIDATE_SUMMARY,
                prior_source_text=self.PRIOR_SOURCE,
                candidate_source_text=self.CANDIDATE_SOURCE,
            )
        )

    def test_exact_source_release_fingerprint_still_rejects_different_months(self) -> None:
        self.assertFalse(
            same_statistical_release_fingerprint(
                self.PRIOR_SOURCE.replace("7월", "6월"),
                self.CANDIDATE_SOURCE,
            )
        )

    def test_exact_source_release_fingerprint_still_rejects_different_releases(self) -> None:
        self.assertFalse(
            same_statistical_release_fingerprint(
                self.PRIOR_SOURCE,
                self.CANDIDATE_SOURCE.replace(
                    "금융기관 가중평균 금리", "소비자동향조사 결과 통계"
                ),
            )
        )

    def test_active_canonical_identity_owner_does_not_read_raw_source_or_generated_surfaces(self) -> None:
        daily = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        owner = Path("insight_desk/production_orchestrator_v2.py").read_text(encoding="utf-8")
        canonical_core = Path("insight_desk/production_identity_core_v2.py").read_text(encoding="utf-8")
        self.assertNotIn("if visible_event_redundant(", daily)
        self.assertNotIn("source_for_event(pair[0]).body", owner)
        self.assertNotIn("legacy_visible_event_redundant", owner)
        self.assertNotIn("legacy_compare_candidate_identity", owner)
        self.assertIn("CanonicalIdentityCore", owner)
        self.assertIn("def _event_surface(event: CanonicalEvent)", canonical_core)


if __name__ == "__main__":
    unittest.main()
