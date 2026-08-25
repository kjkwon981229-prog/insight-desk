from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import unittest

from insight_desk.core import IdentityKey, IdentityPrecheckVerdict, VerificationCheck, precheck_identity
from insight_desk.semantic import judge_same_event_mutual_entailment
from insight_desk.semantic.identity import has_strong_shared_event_anchor
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
LIVE_274_KBO_SHORT = (
    "김민준은 한화전에서 5이닝 4피안타(1피홈런) 2사사구 6탈삼진 1실점을 기록했다."
)
LIVE_274_KBO_LONG = (
    "SSG 김민준은 한화전에서 5이닝 동안 4피안타(1피홈런), 2사사구, "
    "6탈삼진, 1실점으로 호투했다."
)


@dataclass
class FakeVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    calls: int = 0

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        del claim_text, evidence_text
        self.calls += 1
        answer = self.answers.pop(0) if self.answers else None
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=answer,
            error_code=None if answer is not None else "synthetic_unavailable",
            zero_cost=True,
        )


class Live274VisibleRegressionTests(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_interpretation_only_card_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="단기 금리 경로 조정 반영",
            summary="향후 금리 경로 조정 가능성이 시장 가격에 반영됐다는 의미로 풀이된다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_last_month_named_policy_action_is_stale(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="한국은행 기준금리 인상",
            summary="한국은행은 지난 7월 기준금리를 2.50%에서 2.75%로 인상했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_undated_performance_evaluation_is_not_a_current_event(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="아이돌 멤버, 연기자로서 가능성",
            summary="그는 작품에서 섬세한 감정선을 선보이며 연기자로서의 가능성을 드러냈다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_career_profile_is_not_a_current_event(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="이진혁, 가수·배우 활동 영역 확장",
            summary="업텐션 출신 이진혁은 솔로 가수와 배우로 활동 영역을 넓혀왔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_old_roster_removal_with_day_only_date_is_stale(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="한화, 왕옌청 1군 엔트리 제외",
            summary="한화는 지난 21일 왕옌청을 1군 엔트리에서 제외했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_market_event_can_keep_later_interpretive_background(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="원·달러 환율, 25일 반등",
            summary=(
                "원·달러 환율은 25일 장중 1,390원대로 반등했다. "
                "최근 금리 경로 재평가가 시장 가격에 반영됐다는 의미로 풀이된다."
            ),
        )
        self.assertTrue(decision.accepted)

    def test_current_kpop_release_announcement_remains_accepted(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="제니, 28일 신곡 공개",
            summary="제니는 25일 신곡 'Fallen Angel'을 28일 공개한다고 발표했다.",
        )
        self.assertTrue(decision.accepted)

    def test_dated_current_performance_event_is_not_mistaken_for_profile(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="아이돌 멤버, 25일 드라마 첫 방송",
            summary="그룹 멤버는 25일 첫 방송된 드라마에서 주연으로 출연했다.",
        )
        self.assertTrue(decision.accepted)


class Live274KboIdentityRegressionTests(unittest.TestCase):
    def test_player_subject_expansion_is_not_a_deterministic_conflict(self) -> None:
        precheck = precheck_identity(
            IdentityKey(subject_key="김민준", action_key="한화전 5이닝 1실점"),
            IdentityKey(subject_key="SSG 김민준", action_key="한화전 5이닝 1실점"),
        )
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.REQUIRE_LLM_JUDGMENT)
        self.assertNotIn("subject", precheck.conflicting_fields)

    def test_same_pitching_line_has_strong_baseball_event_anchor(self) -> None:
        self.assertTrue(has_strong_shared_event_anchor(LIVE_274_KBO_SHORT, LIVE_274_KBO_LONG))

    def test_same_pitching_line_can_survive_directional_detail_asymmetry(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = FakeVerifier("cloudflare", "failover", [True, False])
        judgment = judge_same_event_mutual_entailment(
            LIVE_274_KBO_LONG,
            LIVE_274_KBO_SHORT,
            primary=primary,
            secondary=local,
        )
        self.assertIs(judgment.same_event, True)
        self.assertEqual(judgment.secondary_checks, 2)
        self.assertEqual(judgment.primary_checks, 2)

    def test_same_player_and_opponent_with_different_pitching_line_is_not_relaxed(self) -> None:
        other_game = "김민준은 한화전에서 6이닝 7피안타 3사사구 4탈삼진 3실점을 기록했다."
        self.assertFalse(has_strong_shared_event_anchor(LIVE_274_KBO_SHORT, other_game))
        local = FakeVerifier("local-nli", "mdeberta", [False])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        judgment = judge_same_event_mutual_entailment(
            LIVE_274_KBO_SHORT,
            other_game,
            primary=primary,
            secondary=local,
        )
        self.assertIs(judgment.same_event, False)
        self.assertEqual(local.calls, 1)
        self.assertEqual(primary.calls, 0)

    def test_same_stat_line_with_different_player_and_opponent_is_not_relaxed(self) -> None:
        unrelated = "박준영은 두산전에서 5이닝 4피안타(1피홈런) 2사사구 6탈삼진 1실점을 기록했다."
        self.assertFalse(has_strong_shared_event_anchor(LIVE_274_KBO_SHORT, unrelated))


if __name__ == "__main__":
    unittest.main()
