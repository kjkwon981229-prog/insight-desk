from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    IdentityKey,
    IdentityPrecheckVerdict,
    VerificationCheck,
    precheck_identity,
)
from insight_desk.semantic import judge_same_event_mutual_entailment
from insight_desk.semantic.identity import has_strong_shared_event_anchor
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
LIVE_266_SHORT = (
    "특히 K-POP 댄스 프로그램에는 SM Universe 강사진이 참여해 안무 지도와 "
    "팀별 공연 준비를 진행했다."
)
LIVE_266_LONG = (
    "특히 K-pop 댄스 프로그램에는 SM 유니버스(Universe)의 강사진이 참여해 "
    "전문적인 안무교육을 진행했다. 참가자들은 팀별 공연을 준비하며 자신감과 "
    "협동심을 키웠다."
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


class Phase12AGLive266Regressions(unittest.TestCase):
    def test_nonannouncement_state_is_not_a_daily_event(self) -> None:
        decision = evaluate_story_admission(
            topic="엔터·음악·K-POP",
            headline="롱샷 향후 앨범 계획 미발표",
            summary="롱샷의 다음 앨범에 대한 계획은 아직 발표되지 않은 상태입니다.",
            source_text="롱샷의 다음 앨범에 대한 계획은 아직 발표되지 않은 상태입니다.",
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_actual_current_announcement_remains_accepted(self) -> None:
        decision = evaluate_story_admission(
            topic="엔터·음악·K-POP",
            headline="롱샷, 새 앨범 발매 계획 발표",
            summary="롱샷은 25일 새 앨범을 10월에 발매한다고 발표했다.",
            source_text="롱샷은 25일 새 앨범을 10월에 발매한다고 발표했다.",
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )
        self.assertTrue(decision.accepted)

    def test_parenthetical_romanization_is_not_a_deterministic_subject_conflict(self) -> None:
        precheck = precheck_identity(
            IdentityKey(
                subject_key="SM 유니버스(Universe)의 강사진",
                action_key="안무교육을 진행했다",
                event_date_key="2026-08-25",
            ),
            IdentityKey(
                subject_key="SM Universe 소속 강사진",
                action_key="안무 지도를 진행했다",
                event_date_key="2026-08-25",
            ),
        )
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.REQUIRE_LLM_JUDGMENT)
        self.assertNotIn("subject", precheck.conflicting_fields)

    def test_genuinely_different_subjects_remain_a_deterministic_block(self) -> None:
        precheck = precheck_identity(
            IdentityKey(subject_key="SM Universe 강사진", action_key="안무 교육"),
            IdentityKey(subject_key="JYP 강사진", action_key="안무 교육"),
        )
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.BLOCK_MERGE)
        self.assertIn("subject", precheck.conflicting_fields)

    def test_live_266_cross_source_pair_has_high_overlap_identity_anchor(self) -> None:
        self.assertTrue(has_strong_shared_event_anchor(LIVE_266_SHORT, LIVE_266_LONG))

    def test_high_overlap_pair_can_survive_directional_detail_asymmetry(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = FakeVerifier("cloudflare", "failover", [True, False])
        judgment = judge_same_event_mutual_entailment(
            LIVE_266_LONG,
            LIVE_266_SHORT,
            primary=primary,
            secondary=local,
        )
        self.assertIs(judgment.same_event, True)
        self.assertEqual(judgment.secondary_checks, 2)
        self.assertEqual(judgment.primary_checks, 2)

    def test_same_provider_different_lessons_do_not_get_the_high_overlap_relaxation(self) -> None:
        dance = "SM Universe 강사진이 K-pop 댄스 프로그램에 참여해 안무 지도를 진행했다."
        vocal = "SM Universe 강사진이 K-pop 보컬 프로그램에 참여해 보컬 지도를 진행했다."
        self.assertFalse(has_strong_shared_event_anchor(dance, vocal))
        local = FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        judgment = judge_same_event_mutual_entailment(
            dance,
            vocal,
            primary=primary,
            secondary=local,
        )
        self.assertIs(judgment.same_event, False)
        self.assertEqual(local.calls, 1)
        self.assertEqual(primary.calls, 0)


if __name__ == "__main__":
    unittest.main()
