from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 25, 12, 40, tzinfo=timezone.utc)


class Live279VisibleRegressionTests(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_institutional_quiet_period_explainer_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="금통위원회의 1주일 의견 비공개 기간",
            summary=(
                "기준금리를 결정하는 금융통화위원회가 열리기 전에 중앙은행 총재 등 "
                "금통위원들이 외부에 의견을 공개하지 않는 약 1주일간의 기간을 가진다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_quiet_period_start_remains_a_current_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="금통위, 25일 의견 비공개 기간 시작",
            summary="한국은행은 25일 금통위원들의 외부 의견 비공개 기간이 시작됐다고 밝혔다.",
        )
        self.assertTrue(decision.accepted)

    def test_undated_causal_analysis_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="한은 체감경기 저하 분석",
            summary=(
                "한은은 양호한 실물경제 흐름에도 국내 증시 조정과 누적된 물가 상승 등으로 "
                "체감경기가 저하된 영향으로 분석했습니다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_report_event_can_keep_causal_analysis_background(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="한국은행, 25일 체감경기 보고서 발표",
            summary=(
                "한국은행은 25일 체감경기 관련 보고서를 발표했다. "
                "보고서는 증시 조정과 누적 물가 상승의 영향으로 분석했다."
            ),
        )
        self.assertTrue(decision.accepted)

    def test_old_in_game_pitching_caption_is_stale(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="KIA-한화전 1회초 왕옌청 투구",
            summary=(
                "18일 대전 한화생명 볼파크에서 열린 2026 KBO리그 KIA 타이거즈와 "
                "한화 이글스의 경기 중 1회초 한화 선발투수 왕옌청이 공을 던지고 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_kbo_result_is_not_mistaken_for_stale_caption(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="한화, 25일 SSG전 승리",
            summary="한화는 25일 인천에서 열린 SSG와의 경기에서 4대2로 승리했다.",
        )
        self.assertTrue(decision.accepted)


if __name__ == "__main__":
    unittest.main()
