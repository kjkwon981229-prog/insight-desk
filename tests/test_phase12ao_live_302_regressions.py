from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 16, 13, tzinfo=timezone.utc)


class Live302VisibleStoryRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_referential_event_without_parent_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="효성중공업, 이번 행사에서 차세대 전력망 토털 솔루션 전시",
            summary=(
                "효성중공업은 이번 행사에서 장거리·대용량 송전 기술인 초고압직류송전(HVDC)부터 "
                "데이터센터용 직류 배전 기술인 반도체 변압기(SST)까지 차세대 전력망을 아우르는 "
                "토털 솔루션을 전시한다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_parent_event_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="효성중공업, CIGRE 2026서 차세대 전력망 솔루션 전시",
            summary=(
                "효성중공업은 25일 프랑스 파리 CIGRE 2026에 참가해 HVDC와 SST 등 "
                "차세대 전력망 토털 솔루션을 전시한다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_subjectless_market_headline_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="경제·투자",
            headline="장 초반 4% 넘게 떨어지며 휘청",
            summary=(
                "25일 하락 출발한 국내 증시는 개인과 기관의 매수세에 장중 낙폭을 회복하면서 "
                "상승 마감했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_market_headline_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·투자",
            headline="코스피, 장중 4% 급락 딛고 상승 전환",
            summary="25일 코스피는 장중 4% 넘게 하락했다가 반등해 6742.74에 상승 마감했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_malformed_three_digit_kbo_league_year_is_rejected(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="김민준, 한화전 선발 등판 5이닝 1실점 호투",
            summary=(
                "김민준은 25일 인천 SSG랜더스필드에서 열린 한화 이글스와 226 신한 SOL KBO리그 "
                "홈경기에 선발 등판해 5이닝 동안 92구를 던지며 1실점을 기록했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.MALFORMED, decision.reasons)

    def test_valid_four_digit_kbo_league_year_remains_accepted(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="김민준, 한화전 선발 등판 5이닝 1실점 호투",
            summary=(
                "김민준은 25일 인천 SSG랜더스필드에서 열린 한화 이글스와 2026 신한 SOL KBO리그 "
                "홈경기에 선발 등판해 5이닝 동안 92구를 던지며 1실점을 기록했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
