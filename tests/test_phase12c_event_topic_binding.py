from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from scripts.phase11_daily_production import event_topic_relevant, load_topics


NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def topic(topic_id: str):
    return next(item for item in load_topics(Path("config/topics.json")) if item.topic_id == topic_id)


def bound_event(text: str, *, topic_id: str = "ai_tech"):
    evidence = EvidenceSpan(
        evidence_id="ev:event-topic",
        article_id="article:event-topic",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    subject, _, action = text.partition(" ")
    fact = EventFact(
        fact_id="fact:event-topic",
        subject=subject.rstrip("은는이가"),
        action=action or text,
        evidence_ids=(evidence.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:event-topic",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(evidence.article_id,),
    )
    return event, {fact.fact_id: fact}, {evidence.evidence_id: evidence}


def relevant(text: str, topic_id: str) -> bool:
    event, facts, evidence = bound_event(text, topic_id=topic_id)
    return event_topic_relevant(
        event=event,
        facts=facts,
        evidence=evidence,
        topic=topic(topic_id),
    )


class Phase12CEventTopicBindingTests(unittest.TestCase):
    def test_canonical_kpop_incidental_article_event_is_rejected(self) -> None:
        self.assertFalse(
            relevant(
                "한국건강가정진흥원이 주최하는 행사는 전국 245개 가족센터와 기업이 참여해 400부스 규모를 운영한다.",
                "kpop",
            )
        )

    def test_canonical_hanwha_topic_does_not_accept_unrelated_dosan_lotte_event(self) -> None:
        self.assertFalse(
            relevant(
                "곽빈은 롯데 자이언츠와의 홈 경기에 선발 등판해 7이닝 무실점으로 두산의 3-1 승리를 이끌었다.",
                "kbo_hanwha",
            )
        )

    def test_canonical_psat_topic_does_not_accept_leet_mock_exam_event(self) -> None:
        self.assertFalse(
            relevant(
                "로스쿨 진학을 준비하는 예비법조인들의 전국 LEET 모의고사는 수험생들이 실전 감각을 강화하는 기회가 됐다.",
                "psat_recruitment",
            )
        )

    def test_ai_article_cannot_publish_non_ai_child_event(self) -> None:
        self.assertFalse(
            relevant(
                "인천관광공사는 시민 의견을 관광사업과 정책에 반영하기 위한 열린혁신 아이디어 공모전을 진행한다고 발표했다.",
                "ai_tech",
            )
        )

    def test_positive_ai_event_keeps_binding(self) -> None:
        self.assertTrue(
            relevant(
                "포항테크노파크가 경북 AI 생태계 조성 민관협력 포럼을 개최했다고 밝혔다.",
                "ai_tech",
            )
        )

    def test_positive_kpop_group_release_keeps_binding(self) -> None:
        self.assertTrue(
            relevant(
                "그룹 키키가 EP 3집을 발매하고 타이틀곡 활동에 나섰다.",
                "kpop",
            )
        )

    def test_korean_bts_alias_is_event_local_kpop_binding(self) -> None:
        self.assertTrue(
            relevant(
                "방탄소년단 지민이 토론토 월드투어 무대에 올랐다.",
                "kpop",
            )
        )

    def test_positive_hanwha_game_event_keeps_binding(self) -> None:
        self.assertTrue(
            relevant(
                "프로야구 LG 트윈스가 한화 이글스를 누르고 3위 자리를 되찾았다.",
                "kbo_hanwha",
            )
        )

    def test_positive_psat_event_keeps_binding(self) -> None:
        self.assertTrue(
            relevant(
                "인사혁신처가 2027년도 국가공무원 5급 공채 PSAT 일정을 발표했다.",
                "psat_recruitment",
            )
        )

    def test_positive_economy_event_keeps_binding(self) -> None:
        self.assertTrue(
            relevant(
                "한국은행이 기준금리를 동결했다고 발표했다.",
                "economy",
            )
        )

    def test_production_selection_recomputes_event_relevance(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn("event_topic_relevant(", source)
        self.assertNotIn("topic_relevant=True,", source)
        self.assertIn("topic_relevant=event_relevant,", source)


if __name__ == "__main__":
    unittest.main()
