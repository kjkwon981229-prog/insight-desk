from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 9, 20, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live369ParentlessTaskRegressions(unittest.TestCase):
    def test_parentless_designated_task_surfaces_are_not_standalone(self) -> None:
        cases = (
            (
                "지정 과제 무인 드론 영상, CCTV AI 모델 개발",
                "지정 과제는 무인 드론 영상 활용 녹조 탐지 알고리즘과 CCTV 영상 분석 기반 도시 침수 및 하천 범람 감지 AI 모델을 개발하는 것이며, 분석에 필요한 데이터가 함께 제공된다.",
            ),
            (
                "선정 과제 스마트팩토리 AI 모델 개발",
                "선정 과제는 제조 현장 이상 탐지 AI 모델을 개발하는 것이다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_program_can_include_its_designated_tasks(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="K-water·가천대, AI for Climate Tech 프로그램 개강",
            summary=(
                "한국수자원공사와 가천대학교는 26일 AI for Climate Tech 프로그램 개강식을 열었다. "
                "프로그램의 지정 과제로 녹조 탐지와 도시 침수 감지 AI 모델 개발이 주어진다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live369UnattributedInterpretationRegressions(unittest.TestCase):
    def test_unattributed_passive_interpretation_is_not_a_publishable_event(self) -> None:
        cases = (
            (
                "한국은행 기준금리 인상 기대",
                "한국은행 금융통화위원회의 기준금리 결정이 하루 앞으로 다가오며 인상 기대도 일부 반영된 것으로 해석된다.",
            ),
            (
                "원화 강세 기대 반영",
                "환율 하락에는 수출 호조에 대한 기대가 일부 반영된 것으로 풀이된다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_analysis_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="신한투자증권, 금리 인상 기대가 채권시장에 반영됐다고 분석",
            summary="신한투자증권은 26일 보고서에서 기준금리 인상 기대가 채권시장에 일부 반영됐다고 분석했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live369SubjectlessCausalRemainderRegressions(unittest.TestCase):
    def test_subjectless_effect_remainders_are_not_standalone(self) -> None:
        cases = (
            (
                "AI 투자에 자금 부담",
                "미국 기업의 회사채 금리를 끌어올리고, 막대한 자금이 필요한 인공지능(AI) 투자에 부담을 준다.",
            ),
            (
                "기업 조달비용 압박",
                "기업의 자금 조달 비용을 높이고 신규 설비 투자에도 부담을 준다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_current_attributed_event_can_include_a_causal_explanation(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="야데니리서치, AI 회사채 증가 영향 분석 발표",
            summary=(
                "야데니리서치는 26일 AI 투자용 회사채 발행 증가의 영향을 분석한 결과를 발표했다. "
                "국채금리 상승은 기업의 조달비용을 높이고 AI 투자에도 부담을 줄 수 있다고 분석했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live369HeadlineScopePreservationRegressions(unittest.TestCase):
    def test_generic_metric_headline_cannot_drop_the_summary_scope_qualifier(self) -> None:
        cases = (
            (
                "상품 금리는 4.76%로 전월보다 0.23%포인트 상승했다",
                "한국은행이 26일 발표한 자료에 따르면 주담대 중 고정형 상품 금리는 4.76%로 전월보다 0.23%포인트 상승했다.",
            ),
            (
                "금리는 5.10%로 전월보다 상승했다",
                "한국은행에 따르면 예금은행 일반신용대출 금리는 5.10%로 전월보다 상승했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_scope_preserving_metric_headline_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="주담대 고정형 상품 금리 4.76%로 상승",
            summary="한국은행이 26일 발표한 자료에 따르면 주담대 중 고정형 상품 금리는 4.76%로 전월보다 0.23%포인트 상승했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live369MediaSynopsisRegressions(unittest.TestCase):
    def test_fiction_or_film_synopsis_is_not_a_kpop_event(self) -> None:
        cases = (
            (
                "작품은 1940~50년대 아바나와 뉴욕, 파리를 배경으로 피아니스트 치코와 가수 리타의 만남과 이별을 그린다",
                "아카데미 장편 애니메이션상 후보에 오른 이 작품은 1940~50년대 아바나와 뉴욕, 파리를 배경으로 피아니스트 치코와 가수 리타의 만남과 이별을 그린다.",
            ),
            (
                "작품은 서울을 배경으로 가수 지망생의 성장과 우정을 그린다",
                "이 영화는 서울을 배경으로 가수 지망생의 성장과 우정을 그린다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="엔터·음악·K-POP", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_kpop_soundtrack_release_can_include_story_context(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="K-POP 그룹 엔하이픈, 애니메이션 OST 공개",
            summary="K-POP 그룹 엔하이픈은 26일 애니메이션 OST를 공개했다. 작품은 청춘의 성장 이야기를 그린다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live369SameDayPastCueRegressions(unittest.TestCase):
    def test_same_day_cannot_be_presented_as_an_unqualified_past_day(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="SSG, 지난 26일 한화전 7-1 승리",
            summary="SSG 랜더스는 지난 26일 인천에서 열린 한화 이글스와의 경기에서 7-1 승리를 거뒀다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_previous_day_current_game_result_remains_publishable(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="SSG, 지난 25일 한화전 7-1 승리",
            summary="SSG 랜더스는 지난 25일 인천에서 열린 한화 이글스와의 경기에서 7-1 승리를 거뒀다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
