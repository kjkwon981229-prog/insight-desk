from __future__ import annotations

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
from insight_desk.production_orchestrator_v2 import (
    canonical_event_from_candidate,
    source_document_from_article,
)
from insight_desk.production_runtime_v2 import production_v2_runtime
import scripts.phase11_daily_production as production


NOW = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)


def _topic(topic_id: str, *, anchors: tuple[str, ...], required: tuple[str, ...]):
    return production._core.TopicConfig(
        topic_id=topic_id,
        name=topic_id,
        priority=1,
        candidate_budget=4,
        selection_cap=3,
        intent_anchors=anchors,
        required_intent_terms=required,
        news_queries=(topic_id,),
        event_terms=("발표", "경기", "시험", "공개"),
    )


def _article(article_id: str, *, title: str, body: str, topic_id: str) -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id=f"web:{article_id}",
            source_name="example.com",
            url=f"https://example.com/{article_id}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title=title,
        body=body,
        topic_ids=(topic_id,),
        query=topic_id,
    )


def _bind_event(
    registry,
    *,
    article: RawArticle,
    topic_id: str,
    evidence_text: str,
    subject: str,
    action: str,
    object_text: str | None = None,
):
    start = article.body.index(evidence_text)
    evidence = EvidenceSpan.from_article(
        evidence_id=f"evidence:{article.article_id}",
        article=article,
        field=EvidenceField.BODY,
        start=start,
        end=start + len(evidence_text),
    )
    fact = EventFact(
        fact_id=f"fact:{article.article_id}",
        subject=subject,
        action=action,
        object=object_text,
        evidence_ids=(evidence.evidence_id,),
    )
    event = CandidateEvent(
        event_id=f"event:{article.article_id}",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(article.article_id,),
    )
    source = source_document_from_article(article)
    registry.sources_by_article[article.article_id] = source
    registry.events_by_id[event.event_id] = canonical_event_from_candidate(
        event,
        facts={fact.fact_id: fact},
        source=source,
    )
    return event, fact, evidence


class Live464EventRelevanceHandoffRegressions(unittest.TestCase):
    def test_article_relevance_does_not_auto_authorize_unrelated_event_evidence(self) -> None:
        cases = (
            (
                _topic("kpop", anchors=("K-POP", "아이돌"), required=("아이돌", "앨범")),
                "K-POP 산업 동향과 함께 방송사 신규 프로그램도 소개했다.",
                "방송사는 새로운 연애 예능을 공개했다.",
                "방송사",
                "새로운 연애 예능을 공개했다",
            ),
            (
                _topic("kbo_hanwha", anchors=("한화", "KBO"), required=("한화",)),
                "한화 이글스 소식과 함께 다른 구단의 투수 보직 변화도 전했다.",
                "롯데 투수는 마무리 보직에서 내려왔다.",
                "롯데 투수",
                "마무리 보직에서 내려왔다",
            ),
            (
                _topic("psat_recruitment", anchors=("공무원", "PSAT"), required=("공무원", "PSAT")),
                "공무원 시험 관련 소식과 함께 대학 학과 개편도 소개했다.",
                "대학교 행정학과는 독립 학과로 개편된다.",
                "대학교 행정학과",
                "독립 학과로 개편된다",
            ),
        )

        with production_v2_runtime(production._core) as registry:
            for index, (topic, prefix, event_text, subject, action) in enumerate(cases):
                with self.subTest(topic=topic.topic_id):
                    article = _article(
                        f"unrelated-{index}",
                        title=f"{topic.intent_anchors[0]} 관련 종합 소식",
                        body=f"{prefix} {event_text}",
                        topic_id=topic.topic_id,
                    )
                    self.assertTrue(
                        production._core.topic_relevant(
                            title=article.title,
                            body=article.body,
                            topic=topic,
                        )
                    )
                    event, fact, evidence = _bind_event(
                        registry,
                        article=article,
                        topic_id=topic.topic_id,
                        evidence_text=event_text,
                        subject=subject,
                        action=action,
                    )
                    self.assertFalse(
                        production._core.event_topic_relevant(
                            event=event,
                            facts={fact.fact_id: fact},
                            evidence={evidence.evidence_id: evidence},
                            topic=topic,
                        )
                    )

    def test_event_evidence_with_required_intent_remains_relevant(self) -> None:
        topic = _topic(
            "kbo_hanwha",
            anchors=("한화", "KBO"),
            required=("한화",),
        )
        event_text = "한화 이글스는 SSG와의 경기에서 승리했다."
        article = _article(
            "hanwha-positive",
            title="한화 이글스 경기 결과",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            event, fact, evidence = _bind_event(
                registry,
                article=article,
                topic_id=topic.topic_id,
                evidence_text=event_text,
                subject="한화 이글스",
                action="SSG와의 경기에서 승리했다",
            )
            self.assertTrue(
                production._core.event_topic_relevant(
                    event=event,
                    facts={fact.fact_id: fact},
                    evidence={evidence.evidence_id: evidence},
                    topic=topic,
                )
            )


if __name__ == "__main__":
    unittest.main()
