from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)


class Live282VisibleRegressionTests(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_exhibition_component_description_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="전시 분야 피지컬 AI·자율주행 소프트웨어 등으로 구성",
            summary=(
                "전시 분야는 피지컬 AI·자율주행 소프트웨어, 센서·반도체·전장, "
                "시뮬레이션·검증·인증, 자율주행 모빌리티 서비스, 데이터·지도·공간지능, "
                "로봇·스마트 물류 등으로 구성했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_exhibition_opening_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="자율주행 산업전, 25일 개막",
            summary="자율주행 산업전이 25일 서울에서 개막했다.",
        )
        self.assertTrue(decision.accepted)

    def test_future_intended_use_without_current_action_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="넥서스 홀, 교육 혁신 플랫폼으로 활용 예정",
            summary=(
                "넥서스 홀은 단순한 강의 공간이 아니라 소재, 반도체, 공학 분야의 교육과 "
                "연구를 지원하고 대학과 지역, 산업계를 잇는 교육혁신 플랫폼으로 활용될 예정이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_opening_can_keep_future_use_background(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="넥서스 홀, 25일 개소",
            summary=(
                "울산시는 25일 UNIST 공과대학에 넥서스 홀이 개소했다고 밝혔다. "
                "이 공간은 반도체 교육과 연구 플랫폼으로 활용될 예정이다."
            ),
        )
        self.assertTrue(decision.accepted)

    def test_static_retirement_rule_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="퇴직연금 계좌, 위험자산 투자 한도 70%",
            summary=(
                "근로자퇴직급여보장법 시행령에 따라 퇴직연금 계좌는 주식형 펀드·ETF 등 "
                "위험자산에 적립금의 70%까지만 투자할 수 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_rule_change_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="퇴직연금 위험자산 한도, 25일 상향",
            summary="정부는 25일 시행령을 개정해 퇴직연금 위험자산 투자 한도를 80%로 상향했다.",
        )
        self.assertTrue(decision.accepted)

    def test_referential_album_achievement_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="아이튠즈 차트 110개국 1위 앨범",
            summary=(
                "이 앨범은 아이튠즈 앨범 차트 110개국 1위를 기록했고, 한터차트 기준 "
                "초동 210만 장 이상을 달성해 더블 밀리언셀러에 올랐다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_album_chart_event_remains_accepted(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="그룹 신보 A 앨범, 25일 아이튠즈 110개국 1위",
            summary="그룹 신보 'A' 앨범은 25일 아이튠즈 앨범 차트 110개국 1위를 기록했다.",
        )
        self.assertTrue(decision.accepted)

    def test_activity_since_career_history_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="이진혁, 그룹 업텐션 이후 솔로 가수·배우로 영역 확대",
            summary="이진혁은 그룹 업텐션 활동 이후 솔로 가수와 배우로 영역을 넓혀왔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_list_order_lead_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="제니, 새 디지털 앨범 ‘Fallen Angel’ 공개",
            summary="가장 먼저, 제니는 오는 28일 새 디지털 앨범 ‘Fallen Angel’을 공개합니다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_clean_current_release_announcement_remains_accepted(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="제니, 새 디지털 앨범 ‘Fallen Angel’ 공개",
            summary="제니는 25일 새 디지털 앨범 ‘Fallen Angel’을 오는 28일 공개한다고 밝혔다.",
        )
        self.assertTrue(decision.accepted)

    def test_trailing_dateline_byline_is_visible_metadata(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="달러-원 환율 1,380원대 중반 반등",
            summary="달러-원 환율이 1,380원대 중반으로 반등했다. (서울=연합인포맥스) 김지연 기자",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_clean_current_fx_move_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="달러-원 환율 1,380원대 중반 반등",
            summary="달러-원 환율이 25일 1,380원대 중반으로 반등했다.",
        )
        self.assertTrue(decision.accepted)

    def test_old_sports_photo_caption_with_comma_surface_is_stale(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="1회초 한화 선발투수 왕옌청이 공을 힘차게 던지고 있다",
            summary=(
                "18일 오후 대전 한화생명 볼파크에서 열린 '2026 신한 SOL Bank KBO리그' "
                "KIA 타이거즈와 한화 이글스의 경기, 1회초 한화 선발투수 왕옌청이 "
                "공을 힘차게 던지고 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_kbo_pitching_result_remains_accepted(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="SSG 김민준, 한화전 선발 5이닝 1실점 호투",
            summary=(
                "25일 인천 SSG랜더스필드에서 열린 2026 신한 SOL Bank KBO리그 "
                "한화 이글스와의 시즌 12차전에 SSG 랜더스 투수 김민준이 선발 등판해 "
                "5이닝 동안 4피안타(1피홈런), 2사사구, 6탈삼진, 1실점을 기록했다."
            ),
        )
        self.assertTrue(decision.accepted)


if __name__ == "__main__":
    unittest.main()
