from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EventFact, IdentityKey, IdentityPrecheckVerdict, precheck_identity
from insight_desk.semantic import compare_candidate_identity
from scripts.phase11_daily_production import load_topics, topic_relevant


class Phase12ILiveAcceptanceRegressions(unittest.TestCase):
    def test_kpop_company_name_suffix_group_is_not_sufficient_topic_evidence(self) -> None:
        kpop = next(topic for topic in load_topics(Path("config/topics.json")) if topic.topic_id == "kpop")
        self.assertFalse(
            topic_relevant(
                title="피스챌린지그룹, 영화감독 이채영 지원 방침",
                body=(
                    "차영철 피스챌린지그룹 회장은 이채영이 글로벌 영화감독으로 성장하도록 "
                    "국내외 콘텐츠 시장 내 활동을 지원하겠다고 밝혔다."
                ),
                topic=kpop,
            )
        )

    def test_kpop_real_group_release_keeps_strong_music_binding(self) -> None:
        kpop = next(topic for topic in load_topics(Path("config/topics.json")) if topic.topic_id == "kpop")
        self.assertTrue(
            topic_relevant(
                title="그룹 키키, EP 3집 발매",
                body="그룹 키키가 새 앨범 EP 3집을 발매하고 타이틀곡 활동에 나섰다.",
                topic=kpop,
            )
        )

    def test_descriptor_only_subject_expansion_reaches_semantic_identity_review(self) -> None:
        left_fact = EventFact(
            fact_id="fact:left",
            subject="공간 AX 기업 HDC랩스",
            action="AI 홈 에이전트 기반 스마트홈 서비스를 확대한다고 밝혔다",
            evidence_ids=("ev:left",),
        )
        right_fact = EventFact(
            fact_id="fact:right",
            subject="공간 AX 솔루션 기업 HDC랩스",
            action="AI 홈 에이전트를 중심으로 스마트홈 솔루션 고도화에 나선다",
            evidence_ids=("ev:right",),
        )
        left = CandidateEvent(
            event_id="event:left",
            topic_id="ai_tech",
            fact_ids=(left_fact.fact_id,),
            article_ids=("article:left",),
        )
        right = CandidateEvent(
            event_id="event:right",
            topic_id="ai_tech",
            fact_ids=(right_fact.fact_id,),
            article_ids=("article:right",),
        )
        decision = compare_candidate_identity(
            left,
            right,
            {left_fact.fact_id: left_fact, right_fact.fact_id: right_fact},
            semantic_same_event=None,
        )
        self.assertFalse(decision.deterministic_block)
        self.assertIsNone(decision.same_event)
        self.assertEqual(decision.reason, "identity_unresolved")

    def test_genuinely_different_subjects_remain_a_hard_conflict(self) -> None:
        precheck = precheck_identity(
            IdentityKey(subject_key="company-a", action_key="invest"),
            IdentityKey(subject_key="company-b", action_key="invest"),
        )
        self.assertEqual(precheck.verdict, IdentityPrecheckVerdict.BLOCK_MERGE)
        self.assertIn("subject", precheck.conflicting_fields)


if __name__ == "__main__":
    unittest.main()
