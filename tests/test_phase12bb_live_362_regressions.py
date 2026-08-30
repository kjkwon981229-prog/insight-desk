from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.feed_quality_detectors import visible_metadata_text
from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 8, 10, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live362DeicticEventIdentityRegressions(unittest.TestCase):
    def test_live_and_generalized_unnamed_events_are_not_standalone(self) -> None:
        cases = (
            (
                "생성형 AI 활용 17회 대회",
                "올해로 17회째를 맞는 이번 대회는 참가자들이 생성형 AI로 문제를 분석하는 데 초점을 맞췄다.",
            ),
            (
                "지역 산업 전시 5회 개최",
                "올해로 5회째를 맞는 이번 박람회는 지역 기업의 기술을 소개한다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_event_resolves_later_deictic_reference(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="한국AI교육협회, 생성형 AI 활용 대회 개최",
            summary=(
                "한국AI교육협회는 26일 생성형 AI 활용 대회를 열었다. "
                "이번 대회에는 학생 100명이 참가했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live362VisibleChromeRegressions(unittest.TestCase):
    def test_live_and_generalized_source_chrome_is_metadata(self) -> None:
        cases = (
            "충남도 제공",
            "부산시 제공",
            (
                "매일일보 = 조남상 기자 | 천안시가 내달 2일부터 닷새간 "
                "2026 천안 K-컬처 박람회를 개최한다."
            ),
            "서울신문 = 홍길동 기자 | 서울시가 26일 지원 계획을 발표했다.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(visible_metadata_text(text))
                decision = visible(topic="AI·테크", headline="지역 소식", summary=text)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_local_government_and_publisher_as_real_actors_remain_visible(self) -> None:
        cases = (
            "충남도는 26일 첨단산업 육성방안을 발표했다.",
            "매일일보는 26일 신규 편집국장 인사를 발표했다.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertFalse(visible_metadata_text(text))


class Live362KboLineupIdentityRegressions(unittest.TestCase):
    @staticmethod
    def redundant(
        *,
        prior_headline: str,
        prior_summary: str,
        candidate_headline: str,
        candidate_summary: str,
    ) -> bool:
        return visible_event_redundant(
            topic_id="kbo_hanwha",
            prior_headline=prior_headline,
            prior_summary=prior_summary,
            candidate_headline=candidate_headline,
            candidate_summary=candidate_summary,
        )

    def test_live_and_generalized_same_day_lineup_siblings_are_redundant(self) -> None:
        cases = (
            dict(
                prior_headline="한화 이글스, 26일 선발 라인업 발표",
                prior_summary="2연패 중인 한화 이글스가 26일 선발 라인업을 공개했다.",
                candidate_headline="한화, 26일 경기 선발 라인업 발표",
                candidate_summary=(
                    "한화는 26일 경기에서 김태연, 문현빈, 한지윤, 강백호, "
                    "노시환 순으로 선발 라인업을 꾸렸다."
                ),
            ),
            dict(
                prior_headline="한화, 27일 선발 타순 공개",
                prior_summary="한화가 27일 SSG전에 나설 선발 라인업을 발표했다.",
                candidate_headline="한화 이글스 27일 선발 명단 확정",
                candidate_summary="한화 이글스는 27일 경기 선발 타순을 확정했다.",
            ),
        )
        for case in cases:
            with self.subTest(candidate=case["candidate_headline"]):
                self.assertTrue(self.redundant(**case))

    def test_different_team_or_day_lineups_remain_distinct(self) -> None:
        common = dict(
            prior_headline="한화, 26일 선발 라인업 발표",
            prior_summary="한화는 26일 경기 선발 라인업을 공개했다.",
        )
        cases = (
            dict(
                candidate_headline="한화, 27일 선발 라인업 발표",
                candidate_summary="한화는 27일 경기 선발 라인업을 공개했다.",
            ),
            dict(
                candidate_headline="SSG, 26일 선발 라인업 발표",
                candidate_summary="SSG는 26일 경기 선발 라인업을 공개했다.",
            ),
        )
        for case in cases:
            with self.subTest(candidate=case["candidate_headline"]):
                self.assertFalse(self.redundant(**common, **case))


if __name__ == "__main__":
    unittest.main()
