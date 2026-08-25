from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation_core import (
    GeneratedDraft,
    GenerationRequest,
    PreservationIssueCode,
    validate_preservation,
)
from insight_desk.semantic.baseball_identity import same_game_result_fingerprint
from insight_desk.semantic.events import compare_candidate_identity
from insight_desk.semantic.identity import has_strong_shared_event_anchor, resolve_candidate_pair
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 25, 13, 35, tzinfo=timezone.utc)


class Live289VisibleRegressionTests(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_static_safe_asset_classification_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="채권혼합형 펀드·ETF의 안전자산 분류 및 편입 한도",
            summary=(
                "채권혼합형 펀드와 ETF는 안전자산으로 분류됨에 따라 주식 투자한도 규제에서 "
                "제외되어 자산총액의 100%까지 편입이 가능하다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_safe_asset_rule_change_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="정부, 25일 퇴직연금 안전자산 편입 규정 개정",
            summary=(
                "정부는 25일 시행령을 개정해 채권혼합형 ETF의 안전자산 편입 기준을 변경했다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted)

    def test_ai_trend_strategy_without_current_event_is_not_daily_news(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="고성능 맥, AI 개발 핵심 플랫폼",
            summary=(
                "AI 에이전트와 LLM을 개인 컴퓨터에서 직접 구동하려는 개발자와 연구자가 늘어나며, "
                "고성능 데스크톱 맥을 AI 개발 핵심 플랫폼으로 키우려는 전략이 등장했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_ai_platform_announcement_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="애플, 25일 맥용 AI 개발 플랫폼 공개",
            summary="애플은 25일 고성능 맥에서 AI 모델을 개발할 수 있는 플랫폼을 공개했다.",
        )
        self.assertTrue(decision.accepted)

    def test_promotional_multi_artist_comeback_rollup_is_not_one_event(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="제니·리사·지수 연이은 컴백 소식",
            summary=(
                "제니부터 리사, 지수까지 이어지는 컴백 소식이 이번 여름의 끝자락을 "
                "특별하게 장식하고 있습니다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_single_named_current_release_announcement_remains_accepted(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="제니, 새 디지털 앨범 공개 일정 발표",
            summary="제니는 25일 새 디지털 앨범을 오는 28일 공개한다고 밝혔다.",
        )
        self.assertTrue(decision.accepted)


class Live289KboIdentityRegressionTests(unittest.TestCase):
    @staticmethod
    def _pair(*, right_day: str = "25일", right_city: str = "인천", right_score: str = "1대 7"):
        left_fact = EventFact(
            fact_id="left",
            subject="SSG",
            action="25일 인천 SSG랜더스필드에서 한화 이글스와의 홈 경기에서 7대1로 승리했다",
            evidence_ids=("e-left",),
            event_date="2026-08-25",
            location="인천 SSG랜더스필드",
            participants=("SSG", "한화 이글스"),
        )
        right_fact = EventFact(
            fact_id="right",
            subject="한화",
            action=(
                f"{right_day} {right_city} SSG랜더스필드에서 열린 SSG와의 원정 경기에서 "
                f"{right_score}로 졌다"
            ),
            evidence_ids=("e-right",),
            event_date="2026-08-25" if right_day == "25일" else "2026-08-24",
            location=f"{right_city} SSG랜더스필드",
            participants=("한화", "SSG"),
        )
        left = CandidateEvent("left-event", "kbo_hanwha", ("left",), ("a-left",))
        right = CandidateEvent("right-event", "kbo_hanwha", ("right",), ("a-right",))
        return left, right, {"left": left_fact, "right": right_fact}

    def test_opposite_team_perspectives_of_same_game_reach_semantic_identity(self) -> None:
        left, right, facts = self._pair()
        decision = compare_candidate_identity(left, right, facts, semantic_same_event=None)
        self.assertFalse(decision.deterministic_block)
        self.assertFalse(decision.same_event)

    def test_reciprocal_same_game_score_is_a_strong_shared_event_anchor(self) -> None:
        left = "SSG가 25일 인천에서 한화와의 경기에서 7대1로 승리했다."
        right = "한화가 25일 인천에서 SSG와의 경기에서 1대7로 졌다."
        self.assertTrue(same_game_result_fingerprint(left, right))
        self.assertTrue(has_strong_shared_event_anchor(left, right))

    def test_positive_semantic_judgment_merges_opposite_game_perspectives(self) -> None:
        left, right, facts = self._pair()
        resolution = resolve_candidate_pair(left, right, facts, semantic_same_event=True)
        self.assertTrue(resolution.decision.same_event)
        self.assertEqual(len(resolution.events), 1)

    def test_different_day_remains_separate(self) -> None:
        left, right, facts = self._pair(right_day="24일")
        self.assertFalse(
            same_game_result_fingerprint(
                "SSG가 25일 인천에서 한화에 7대1로 승리했다.",
                "한화가 24일 인천에서 SSG에 1대7로 졌다.",
            )
        )
        decision = compare_candidate_identity(left, right, facts, semantic_same_event=True)
        self.assertTrue(decision.deterministic_block)
        self.assertFalse(decision.same_event)

    def test_different_location_remains_separate(self) -> None:
        left, right, facts = self._pair(right_city="대전")
        self.assertFalse(
            same_game_result_fingerprint(
                "SSG가 25일 인천에서 한화에 7대1로 승리했다.",
                "한화가 25일 대전에서 SSG에 1대7로 졌다.",
            )
        )
        decision = compare_candidate_identity(left, right, facts, semantic_same_event=True)
        self.assertTrue(decision.deterministic_block)
        self.assertFalse(decision.same_event)


class Live289OutcomeFinalityRegressionTests(unittest.TestCase):
    @staticmethod
    def _request(source: str) -> GenerationRequest:
        evidence = EvidenceSpan(
            evidence_id="e1",
            article_id="a1",
            field=EvidenceField.BODY,
            start=0,
            end=len(source),
            text=source,
        )
        fact = EventFact(
            fact_id="f1",
            subject="SSG",
            action=source,
            evidence_ids=("e1",),
        )
        event = CandidateEvent("event", "kbo_hanwha", ("f1",), ("a1",))
        return GenerationRequest(event=event, facts={"f1": fact}, evidence={"e1": evidence})

    def test_intermediate_score_cannot_be_promoted_to_final_win(self) -> None:
        source = "SSG는 7회초 추가점을 내며 한화에 7-1로 달아났다."
        request = self._request(source)
        draft = GeneratedDraft(
            event_id="event",
            headline="SSG, 한화 상대로 7-1 승리",
            summary="SSG가 한화를 7-1로 꺾었다.",
            evidence_ids=("e1",),
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn(PreservationIssueCode.OUTCOME_FINALITY_MISMATCH, {item.code for item in report.issues})

    def test_final_score_source_can_be_rewritten_as_final_result(self) -> None:
        source = "SSG는 25일 인천에서 한화를 7-1로 꺾고 승리했다."
        request = self._request(source)
        draft = GeneratedDraft(
            event_id="event",
            headline="SSG, 한화전 7-1 승리",
            summary="SSG가 25일 인천에서 한화를 7-1로 꺾고 승리했다.",
            evidence_ids=("e1",),
        )
        report = validate_preservation(request, draft)
        self.assertTrue(report.accepted, report.issues)


if __name__ == "__main__":
    unittest.main()
