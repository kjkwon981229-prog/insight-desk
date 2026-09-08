from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EventFact, RelevanceVerdict
from insight_desk.production_relevance_v2 import event_relevance_decision


@dataclass(frozen=True)
class _Token:
    surface: str
    tag: str
    start: int
    end: int


class _Morphology:
    def analyze(self, text: str):
        if text == "신청해 다시 높아진 공무원 시험의 인기를 보여줬다":
            parts = (
                ("신청해", "VV"),
                ("다시", "MAG"),
                ("높아진", "VA"),
                ("공무원", "NNG"),
                ("시험", "NNG"),
                ("의", "JKG"),
                ("인기", "NNG"),
                ("를", "JKO"),
                ("보여줬다", "VV"),
            )
        elif text == "7급 공채 PSAT 시행 일정을 발표했다":
            parts = (
                ("7급", "NNG"),
                ("공채", "NNG"),
                ("PSAT", "SL"),
                ("시행", "NNG"),
                ("일정", "NNG"),
                ("을", "JKO"),
                ("발표했다", "VV"),
            )
        elif text == "기준금리를 결정했다":
            parts = (("기준금리", "NNG"), ("를", "JKO"), ("결정했다", "VV"))
        elif text == "새 앨범을 공개했다":
            parts = (("새", "MM"), ("앨범", "NNG"), ("을", "JKO"), ("공개했다", "VV"))
        else:
            parts = tuple((value, "NNG") for value in text.split())
        cursor = 0
        output = []
        for surface, tag in parts:
            start = text.find(surface, cursor)
            if start < 0:
                start = cursor
            end = start + len(surface)
            output.append(_Token(surface=surface, tag=tag, start=start, end=end))
            cursor = end
        return tuple(output)


@dataclass(frozen=True)
class _Topic:
    topic_id: str
    intent_anchors: tuple[str, ...]
    required_intent_terms: tuple[str, ...]
    event_terms: tuple[str, ...]


def _event(topic_id: str, fact: EventFact) -> CandidateEvent:
    return CandidateEvent(
        event_id="event-1",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=("article-1",),
    )


class EventRelevanceDirectBindingTests(unittest.TestCase):
    def test_topic_term_only_inside_genitive_background_clause_defers(self) -> None:
        topic = _Topic(
            topic_id="civil_service_fixture",
            intent_anchors=("공무원 시험", "PSAT"),
            required_intent_terms=("공무원 시험",),
            event_terms=("시험", "공채", "시행", "발표"),
        )
        fact = EventFact(
            fact_id="fact-1",
            subject="6,901명",
            action="신청해 다시 높아진 공무원 시험의 인기를 보여줬다",
            evidence_ids=("ev-1",),
        )
        decision = event_relevance_decision(
            event=_event(topic.topic_id, fact),
            facts={fact.fact_id: fact},
            topic=topic,
            morphology=_Morphology(),
        )
        self.assertEqual(decision.verdict, RelevanceVerdict.DEFER)
        self.assertTrue(decision.requires_resolution)

    def test_direct_psat_schedule_event_is_relevant(self) -> None:
        topic = _Topic(
            topic_id="civil_service_fixture",
            intent_anchors=("PSAT", "7급 공채"),
            required_intent_terms=("7급 공채",),
            event_terms=("공채", "시행", "일정", "발표"),
        )
        fact = EventFact(
            fact_id="fact-1",
            subject="인사혁신처",
            action="7급 공채 PSAT 시행 일정을 발표했다",
            evidence_ids=("ev-1",),
        )
        decision = event_relevance_decision(
            event=_event(topic.topic_id, fact),
            facts={fact.fact_id: fact},
            topic=topic,
            morphology=_Morphology(),
        )
        self.assertEqual(decision.verdict, RelevanceVerdict.RELEVANT)

    def test_direct_economy_policy_event_is_relevant(self) -> None:
        topic = _Topic(
            topic_id="economy_fixture",
            intent_anchors=("한국은행", "기준금리"),
            required_intent_terms=(),
            event_terms=("기준금리", "발표"),
        )
        fact = EventFact(
            fact_id="fact-1",
            subject="한국은행 금융통화위원회",
            action="기준금리를 결정했다",
            object="기준금리",
            evidence_ids=("ev-1",),
        )
        decision = event_relevance_decision(
            event=_event(topic.topic_id, fact),
            facts={fact.fact_id: fact},
            topic=topic,
            morphology=_Morphology(),
        )
        self.assertEqual(decision.verdict, RelevanceVerdict.RELEVANT)

    def test_direct_music_release_event_is_relevant(self) -> None:
        topic = _Topic(
            topic_id="music_fixture",
            intent_anchors=("앨범",),
            required_intent_terms=("앨범",),
            event_terms=("앨범", "공개"),
        )
        fact = EventFact(
            fact_id="fact-1",
            subject="그룹 오로라",
            action="새 앨범을 공개했다",
            object="앨범",
            evidence_ids=("ev-1",),
        )
        decision = event_relevance_decision(
            event=_event(topic.topic_id, fact),
            facts={fact.fact_id: fact},
            topic=topic,
            morphology=_Morphology(),
        )
        self.assertEqual(decision.verdict, RelevanceVerdict.RELEVANT)


if __name__ == "__main__":
    unittest.main()
