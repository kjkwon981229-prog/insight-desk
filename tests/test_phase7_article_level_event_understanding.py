from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.core.event_understanding_v2 import ArticleEventRole, TopicRelation, UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_article_understanding,
)


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Token:
    surface: str
    tag: str
    start: int = 0
    end: int = 1


class _Morphology:
    def analyze(self, text: str):
        if text in {"박준영", "한화", "한화와 NC", "앤트로픽", "한화 이글스와 NC 다이노스"}:
            return (_Token(text, "NNP", 0, max(1, len(text))),)
        if text in {"에이전트", "교육업체", "지난 6월과 7월 설명회", "설명회", "시험"}:
            return (_Token(text, "NNG", 0, max(1, len(text))),)
        if text == "공직 수행에 필요한 공통 역량을 평가하는 시험이다":
            return (
                _Token("평가", "NNG", 0, 2),
                _Token("하", "XSV", 2, 3),
                _Token("시험", "NNG", 3, 5),
                _Token("이", "VCP", 5, 6),
            )
        return (_Token(text, "VV", 0, max(1, len(text))),)


def _article(*, title: str, body: str, topic: str) -> RawArticle:
    return RawArticle(
        article_id="article-1",
        provenance=SourceProvenance(
            source_id="web:fixture",
            source_name="fixture",
            url="https://example.com/fresh",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title=title,
        body=body,
        topic_ids=(topic,),
        query=topic,
    )


def _event_fact(
    article: RawArticle,
    *,
    suffix: str,
    sentence: str,
    subject: str,
    action: str,
    topic: str,
    event_date: str | None = None,
) -> tuple[CandidateEvent, EventFact, EvidenceSpan]:
    start = article.body.index(sentence)
    span = EvidenceSpan.from_article(
        evidence_id=f"ev:{suffix}",
        article=article,
        field=EvidenceField.BODY,
        start=start,
        end=start + len(sentence),
    )
    fact = EventFact(
        fact_id=f"fact:{suffix}",
        subject=subject,
        action=action,
        event_date=event_date,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=f"event:{suffix}",
        topic_id=topic,
        fact_ids=(fact.fact_id,),
        article_ids=(article.article_id,),
    )
    return event, fact, span


class ArticleLevelEventUnderstandingTests(unittest.TestCase):
    def _assess(self, article: RawArticle, triples):
        events = tuple(item[0] for item in triples)
        facts = {item[1].fact_id: item[1] for item in triples}
        evidence = {item[2].evidence_id: item[2] for item in triples}
        return assess_compatibility_article_understanding(
            article,
            events=events,
            facts=facts,
            evidence=evidence,
            morphology=_Morphology(),
            now=NOW,
        )

    def test_later_lineup_fact_is_context_when_title_and_lead_center_on_different_event(self) -> None:
        article = _article(
            topic="kbo_hanwha",
            title="박준영 선발, 감독 신뢰 속 NC전 출격",
            body=(
                "박준영은 감독의 신뢰 속 NC전에 선발 등판한다.\n"
                "경기 준비 상황과 최근 투구 내용도 소개됐다.\n"
                "한화는 경기 전 선발 라인업을 발표했다."
            ),
        )
        central = _event_fact(article, suffix="central", sentence="박준영은 감독의 신뢰 속 NC전에 선발 등판한다.", subject="박준영", action="감독의 신뢰 속 NC전에 선발 등판한다", topic="kbo_hanwha")
        lineup = _event_fact(article, suffix="lineup", sentence="한화는 경기 전 선발 라인업을 발표했다.", subject="한화", action="경기 전 선발 라인업을 발표했다", topic="kbo_hanwha")
        result = self._assess(article, (central, lineup))
        self.assertEqual(result[central[0].event_id].article_role, ArticleEventRole.PRIMARY)
        self.assertTrue(result[central[0].event_id].publishable_event)
        self.assertEqual(result[lineup[0].event_id].article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(result[lineup[0].event_id].publishable_event)

    def test_preview_team_stat_is_context_when_scheduled_game_is_article_center(self) -> None:
        article = _article(
            topic="kbo_hanwha",
            title="한화-NC 맞대결 프리뷰, 선발 투수와 경기 전망",
            body=(
                "한화와 NC는 29일 대전에서 맞붙는다.\n"
                "양 팀 선발 투수와 경기 흐름을 전망한다.\n"
                "한화는 팀 타율 리그 3위와 136홈런을 기록 중이다."
            ),
        )
        game = _event_fact(article, suffix="game", sentence="한화와 NC는 29일 대전에서 맞붙는다.", subject="한화와 NC", action="29일 대전에서 맞붙는다", topic="kbo_hanwha")
        stat = _event_fact(article, suffix="stat", sentence="한화는 팀 타율 리그 3위와 136홈런을 기록 중이다.", subject="한화", action="팀 타율 리그 3위와 136홈런을 기록 중이다", topic="kbo_hanwha")
        result = self._assess(article, (game, stat))
        self.assertEqual(result[game[0].event_id].article_role, ArticleEventRole.PRIMARY)
        self.assertEqual(result[stat[0].event_id].article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(result[stat[0].event_id].publishable_event)

    def test_past_attendance_metric_is_context_inside_current_support_program_article(self) -> None:
        article = _article(
            topic="psat_recruitment",
            title="수험 지원 프로그램 확대, 하반기 설명회 운영",
            body=(
                "교육업체는 하반기 수험 지원 프로그램을 확대 운영한다고 밝혔다.\n"
                "지원 프로그램에는 상담과 설명회가 포함된다.\n"
                "지난 6월과 7월 설명회에는 6,901명이 신청했다."
            ),
        )
        program = _event_fact(article, suffix="program", sentence="교육업체는 하반기 수험 지원 프로그램을 확대 운영한다고 밝혔다.", subject="교육업체", action="하반기 수험 지원 프로그램을 확대 운영한다고 밝혔다", topic="psat_recruitment")
        attendance = _event_fact(article, suffix="attendance", sentence="지난 6월과 7월 설명회에는 6,901명이 신청했다.", subject="지난 6월과 7월 설명회", action="6,901명이 신청했다", topic="psat_recruitment")
        result = self._assess(article, (program, attendance))
        self.assertEqual(result[program[0].event_id].article_role, ArticleEventRole.PRIMARY)
        self.assertEqual(result[attendance[0].event_id].article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(result[attendance[0].event_id].publishable_event)

    def test_deep_body_generic_title_match_cannot_be_primary_when_article_center_was_not_extracted(self) -> None:
        article = _article(
            topic="psat_recruitment",
            title="수험 지원 확대, 7·9급 설명회·교재·멘토링 진행",
            body=(
                "교육 브랜드는 교재 출간과 통합 설명회, 멘토링 프로그램을 마련했다고 밝혔다.\n"
                "설명회에는 지난 두 달간 6,901명이 신청했다."
            ),
        )
        attendance = _event_fact(
            article,
            suffix="generic-title-only",
            sentence="설명회에는 지난 두 달간 6,901명이 신청했다.",
            subject="설명회",
            action="지난 두 달간 6,901명이 신청했다",
            topic="psat_recruitment",
        )
        result = self._assess(article, (attendance,))
        decision = result[attendance[0].event_id]
        self.assertEqual(decision.status, UnderstandingStatus.UNRESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(decision.publishable_event)

    def test_generic_secondary_actor_does_not_beat_named_title_bound_primary_actor(self) -> None:
        article = _article(
            topic="ai_tech",
            title="앤트로픽, 로봇 제어용 하드웨어 표준 공개",
            body=(
                "앤트로픽은 로봇 제어용 하드웨어 표준을 공개했다.\n"
                "에이전트는 실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다."
            ),
        )
        named = _event_fact(article, suffix="named", sentence="앤트로픽은 로봇 제어용 하드웨어 표준을 공개했다.", subject="앤트로픽", action="로봇 제어용 하드웨어 표준을 공개했다", topic="ai_tech")
        generic = _event_fact(article, suffix="generic", sentence="에이전트는 실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다.", subject="에이전트", action="실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다", topic="ai_tech")
        result = self._assess(article, (named, generic))
        self.assertEqual(result[named[0].event_id].status, UnderstandingStatus.RESOLVED)
        self.assertEqual(result[named[0].event_id].article_role, ArticleEventRole.PRIMARY)
        self.assertEqual(result[generic[0].event_id].article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(result[generic[0].event_id].publishable_event)

    def test_generic_lead_does_not_beat_later_title_bound_named_actor(self) -> None:
        article = _article(
            topic="ai_tech",
            title="앤트로픽, 로봇 제어용 하드웨어 표준 공개",
            body=(
                "에이전트는 실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다.\n"
                "앤트로픽은 로봇 제어용 하드웨어 표준을 공개했다."
            ),
        )
        generic = _event_fact(article, suffix="generic-lead", sentence="에이전트는 실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다.", subject="에이전트", action="실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다", topic="ai_tech")
        named = _event_fact(article, suffix="named-later", sentence="앤트로픽은 로봇 제어용 하드웨어 표준을 공개했다.", subject="앤트로픽", action="로봇 제어용 하드웨어 표준을 공개했다", topic="ai_tech")
        result = self._assess(article, (generic, named))
        self.assertEqual(result[named[0].event_id].article_role, ArticleEventRole.PRIMARY)
        self.assertTrue(result[named[0].event_id].publishable_event)
        self.assertEqual(result[generic[0].event_id].article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(result[generic[0].event_id].publishable_event)

    def test_copular_definition_is_context_not_a_publishable_event(self) -> None:
        article = _article(
            topic="psat_recruitment",
            title="채용시험 운영 방향 개편 확정",
            body=(
                "담당 기관은 내년 채용시험 운영 방향을 확정했다.\n"
                "시험은 공직 수행에 필요한 공통 역량을 평가하는 시험이다."
            ),
        )
        definition = _event_fact(
            article,
            suffix="definition",
            sentence="시험은 공직 수행에 필요한 공통 역량을 평가하는 시험이다.",
            subject="시험",
            action="공직 수행에 필요한 공통 역량을 평가하는 시험이다",
            topic="psat_recruitment",
        )
        result = self._assess(article, (definition,))
        decision = result[definition[0].event_id]
        self.assertEqual(decision.status, UnderstandingStatus.RESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.CONTEXT)
        self.assertEqual(decision.topic_relation, TopicRelation.BACKGROUND)
        self.assertFalse(decision.publishable_event)

    def test_explicitly_old_event_inside_fresh_article_is_context(self) -> None:
        article = _article(
            topic="kbo_hanwha",
            title="김주원, 한화전 결승 홈런으로 NC 승리 견인",
            body=(
                "한화 이글스와 NC 다이노스는 7일 앞선 경기에서 맞붙었다.\n"
                "김주원은 한화전에서 결승 홈런을 쳐 팀 승리를 이끌었다."
            ),
        )
        old_context = _event_fact(
            article,
            suffix="old-caption",
            sentence="한화 이글스와 NC 다이노스는 7일 앞선 경기에서 맞붙었다.",
            subject="한화 이글스와 NC 다이노스",
            action="7일 앞선 경기에서 맞붙었다",
            topic="kbo_hanwha",
            event_date="2026-08-07",
        )
        result = self._assess(article, (old_context,))
        decision = result[old_context[0].event_id]
        self.assertEqual(decision.status, UnderstandingStatus.RESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.CONTEXT)
        self.assertEqual(decision.topic_relation, TopicRelation.BACKGROUND)
        self.assertFalse(decision.publishable_event)


if __name__ == "__main__":
    unittest.main()
