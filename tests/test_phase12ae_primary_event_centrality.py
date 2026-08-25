from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 7, 0, tzinfo=timezone.utc)


class Phase12AEPrimaryEventCentralityTests(unittest.TestCase):
    def decide(self, *, topic: str, headline: str, summary: str, source_text: str = ""):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=source_text or summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_live_252_primary_non_events_are_rejected(self) -> None:
        cases = (
            (
                "AI·테크",
                "루도로보틱스, 휴머노이드 두뇌 개발 목표",
                "올해 3월 미국에 세운 로봇 자회사 루도로보틱스가 사람과 상호작용할 수 있는 휴머노이드 로봇의 '두뇌' 개발을 목표로 한다.",
            ),
            (
                "경제·투자",
                "계약금액 조정 요건",
                "물가변동에 따른 계약금액 조정은 계약 체결 후 90일 경과와 조정률 3% 이상 등의 요건을 충족해야 한다.",
            ),
            (
                "경제·투자",
                "금리 동결 전망 vs 연속 인상 논쟁",
                "7월에 이어 8월에도 금리를 올리면 10월에는 동결할 것이라는 시각이 우세하지만, 근원물가 흐름을 근거로 세 차례 연속 인상 가능성을 봐야 한다는 의견도 맞서고 있다.",
            ),
            (
                "PSAT·공채 일정",
                "행정학과, 공무원 채용시험 체계 변화에 선제적 대응",
                "행정학과는 변화하는 공무원 채용시험 체계에도 선제적으로 대응한다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                decision = self.decide(topic=topic, headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)
                self.assertIn(StoryAdmissionReason.EVENT_CENTRALITY, decision.reasons)

    def test_live_252_current_event_positives_remain_accepted(self) -> None:
        cases = (
            (
                "AI·테크",
                "AI 대민 상담 도입",
                "국민 체감도가 큰 5대 분야에 AI 기반 대민 상담을 도입한다.",
            ),
            (
                "경제·투자",
                "기준금리 동결 전망 79% 응답",
                "응답자의 79%가 이달 금통위에서 기준금리가 동결될 것이라고 응답했다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                self.assertTrue(self.decide(topic=topic, headline=headline, summary=summary).accepted)

    def test_old_information_is_allowed_when_it_is_background_not_primary(self) -> None:
        current_with_background = self.decide(
            topic="AI·테크",
            headline="A사, AI 로봇 신제품 공개",
            summary=(
                "A사가 25일 AI 로봇 신제품을 공개했다. "
                "이 회사는 2025년부터 휴머노이드 두뇌 개발을 목표로 해왔다."
            ),
            source_text=(
                "A사가 25일 AI 로봇 신제품을 공개했다. "
                "이 회사는 2025년부터 휴머노이드 두뇌 개발을 목표로 해왔다."
            ),
        )
        self.assertTrue(current_with_background.accepted)

        policy_with_background = self.decide(
            topic="경제·투자",
            headline="정부, 계약금액 조정 기준 개정안 발표",
            summary=(
                "정부가 25일 계약금액 조정 기준 개정안을 발표했다. "
                "기존 제도는 계약 후 90일과 조정률 3% 요건을 적용해 왔다."
            ),
            source_text=(
                "정부가 25일 계약금액 조정 기준 개정안을 발표했다. "
                "기존 제도는 계약 후 90일과 조정률 3% 요건을 적용해 왔다."
            ),
        )
        self.assertTrue(policy_with_background.accepted)

    def test_primary_non_event_is_not_rescued_by_a_later_current_sentence(self) -> None:
        decision = self.decide(
            topic="AI·테크",
            headline="A사, 휴머노이드 두뇌 개발 목표",
            summary=(
                "A사는 휴머노이드 두뇌 개발을 목표로 한다. "
                "A사는 25일 별도 AI 신제품도 공개했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.EVENT_CENTRALITY, decision.reasons)

    def test_stale_source_event_is_rejected_even_when_visible_summary_omits_date(self) -> None:
        decision = self.decide(
            topic="엔터·음악·K-POP",
            headline="SM Universe 강사진의 K-pop 안무 교육 실시",
            summary=(
                "K-pop 댄스 프로그램에서 SM Universe 강사진이 안무 교육을 진행했으며, "
                "청소년들은 팀별 공연 준비를 통해 협동심과 자신감을 함양했다."
            ),
            source_text=(
                "안산시는 지난 10일 서울 강남구 SM Universe에서 청소년 대상 K-POP 진로체험 프로그램을 운영했다. "
                "SM Universe 강사진이 안무 교육을 진행했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)
        self.assertIn(StoryAdmissionReason.EVENT_CENTRALITY, decision.reasons)


if __name__ == "__main__":
    unittest.main()
