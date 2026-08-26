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


def _topic(
    topic_id: str,
    *,
    anchors: tuple[str, ...],
    required: tuple[str, ...] = (),
):
    return production._core.TopicConfig(
        topic_id=topic_id,
        name=topic_id,
        priority=1,
        candidate_budget=4,
        selection_cap=3,
        intent_anchors=anchors,
        required_intent_terms=required,
        news_queries=(topic_id,),
        event_terms=("발표", "경기", "시험", "승리", "상승"),
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
    participants: tuple[str, ...] = (),
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
        participants=participants,
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


def _relevant(
    registry,
    *,
    topic,
    article: RawArticle,
    evidence_text: str,
    subject: str,
    action: str,
    object_text: str | None = None,
    participants: tuple[str, ...] = (),
) -> bool:
    event, fact, evidence = _bind_event(
        registry,
        article=article,
        topic_id=topic.topic_id,
        evidence_text=evidence_text,
        subject=subject,
        action=action,
        object_text=object_text,
        participants=participants,
    )
    return production._core.event_topic_relevant(
        event=event,
        facts={fact.fact_id: fact},
        evidence={evidence.evidence_id: evidence},
        topic=topic,
    )


class Live467EventTopicOwnershipRegressions(unittest.TestCase):
    def test_article_topic_does_not_transfer_to_unrelated_economy_child_event(self) -> None:
        topic = _topic("economy", anchors=("한국은행", "기준금리", "시장금리"))
        event_text = "대통령은 전국 기초단체장들과 오찬을 진행했다."
        article = _article(
            "economy-incidental-child",
            title="한국은행 기준금리 관련 아침 주요 뉴스",
            body=f"한국은행 기준금리 관련 소식이다. {event_text}",
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertFalse(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="대통령",
                    action="전국 기초단체장들과 오찬을 진행했다",
                )
            )

    def test_incidental_hanwha_mention_in_action_does_not_prove_event_ownership(self) -> None:
        topic = _topic(
            "kbo_hanwha",
            anchors=("한화 이글스", "KBO"),
            required=("한화", "한화 이글스"),
        )
        event_text = "카드사는 한화 이글스 등 여러 제휴처로 제휴 범위를 확대했다."
        article = _article(
            "hanwha-incidental-partner",
            title="한화 이글스 제휴 관련 산업 소식",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertFalse(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="카드사",
                    action="한화 이글스 등 여러 제휴처로 제휴 범위를 확대했다",
                    object_text="제휴 범위",
                )
            )

    def test_contextual_psat_mention_in_action_does_not_prove_event_ownership(self) -> None:
        topic = _topic(
            "psat_recruitment",
            anchors=("PSAT", "공무원 시험", "인사혁신처"),
            required=("PSAT", "공무원 시험", "인사혁신처"),
        )
        event_text = "대학 행정학과는 공무원 시험 제도 변화에 대응해 교육과정을 개편했다."
        article = _article(
            "psat-context-only",
            title="공무원 시험 변화에 맞춘 대학 교육과정 개편",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertFalse(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="대학 행정학과",
                    action="공무원 시험 제도 변화에 대응해 교육과정을 개편했다",
                    object_text="교육과정",
                )
            )

    def test_topic_owned_actor_is_preserved(self) -> None:
        topic = _topic(
            "psat_recruitment",
            anchors=("PSAT", "공무원 시험", "인사혁신처"),
            required=("PSAT", "인사혁신처"),
        )
        event_text = "인사혁신처는 2027년도 PSAT 일정을 발표했다."
        article = _article(
            "psat-owned-actor",
            title="인사혁신처, 2027년도 PSAT 일정 발표",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertTrue(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="인사혁신처",
                    action="2027년도 PSAT 일정을 발표했다",
                    object_text="2027년도 PSAT 일정",
                )
            )

    def test_topic_owned_object_is_preserved_even_when_opponent_is_actor(self) -> None:
        topic = _topic(
            "kbo_hanwha",
            anchors=("한화 이글스", "KBO"),
            required=("한화", "한화 이글스"),
        )
        event_text = "SSG 랜더스는 KBO 경기에서 한화 이글스를 6-1로 제압했다."
        article = _article(
            "hanwha-owned-object",
            title="SSG, 한화 이글스에 6-1 승리",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertTrue(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="SSG 랜더스",
                    action="KBO 경기에서 한화 이글스를 6-1로 제압했다",
                    object_text="한화 이글스",
                )
            )

    def test_no_required_term_topic_preserves_owned_core_actor(self) -> None:
        topic = _topic("economy", anchors=("한국은행", "기준금리", "시장금리"))
        event_text = "시장금리는 장중 상승했다."
        article = _article(
            "economy-owned-actor",
            title="한국은행 관련 금융시장 동향",
            body=event_text,
            topic_id=topic.topic_id,
        )
        with production_v2_runtime(production._core) as registry:
            self.assertTrue(
                _relevant(
                    registry,
                    topic=topic,
                    article=article,
                    evidence_text=event_text,
                    subject="시장금리",
                    action="장중 상승했다",
                )
            )


if __name__ == "__main__":
    unittest.main()
