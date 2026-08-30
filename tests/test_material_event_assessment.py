from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, RawArticle, SourceProvenance
from insight_desk.semantic.kiwi_extractor import KiwiDeterministicFactExtractor
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from insight_desk.semantic.pipeline import SemanticPipeline

HAS_KIWI = importlib.util.find_spec("kiwipiepy") is not None
NOW = datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc)
_EXTRACTOR = None


def extractor() -> KiwiDeterministicFactExtractor:
    global _EXTRACTOR
    if _EXTRACTOR is None:
        _EXTRACTOR = KiwiDeterministicFactExtractor()
    return _EXTRACTOR


def article(body: str) -> RawArticle:
    return RawArticle(
        article_id="material-canary",
        provenance=SourceProvenance(
            source_id="fixture", source_name="fixture", url="https://example.invalid/material",
            retrieved_via="fixture", fetched_at=NOW, published_at=NOW,
        ),
        title="AI 공장 수주", body=body, topic_ids=("ai_tech",),
    )


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def direct_material_assessment(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="ev:direct-material",
        article_id="article:direct-material",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:direct-material",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:direct-material",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


class PublisherNoticeMaterialRegressionTests(unittest.TestCase):
    def test_publisher_usage_notice_is_not_a_material_news_event(self) -> None:
        text = (
            "뉴스1 콘텐츠를 인공지능(AI) 학습용 데이터로 사용하는 것을 포함하여, "
            "사전허가없이 무단 복사, 배포, 전재, 판매하면 민·형사상의 책임이 따를 수 있습니다."
        )
        assessment = direct_material_assessment(
            text,
            subject="뉴스1 콘텐츠",
            action="인공지능(AI) 학습용 데이터로 사용하는 것을 포함하여, 사전허가없이 무단 복사, 배포, 전재, 판매하면 민·형사상의 책임이 따를 수 있습니다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.PUBLISHER_NOTICE_BOILERPLATE,))

    def test_real_copyright_enforcement_event_is_not_mistaken_for_publisher_boilerplate(self) -> None:
        text = "법원이 AI 기업의 무단 데이터 복제에 대해 손해배상 책임을 인정했다."
        assessment = direct_material_assessment(
            text,
            subject="법원",
            action="AI 기업의 무단 데이터 복제에 대해 손해배상 책임을 인정했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


@unittest.skipUnless(HAS_KIWI, "semantic-local optional dependency not installed")
class MaterialEventAssessmentTests(unittest.TestCase):
    def _extract(self, text: str):
        return SemanticPipeline().extract_article(article(text), topic_id="ai_tech", extractor=extractor())

    def test_evidence_bound_explicit_predicate_is_material(self) -> None:
        result = self._extract("네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.")
        assessment = assess_material_event(
            result.events[0], facts={f.fact_id: f for f in result.facts},
            evidence={e.evidence_id: e for e in result.evidence},
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)
        self.assertIs(assessment.selection_signal, True)
        self.assertEqual(assessment.reasons, (MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE,))

    def test_locked_nominal_lineup_is_material_only_by_frozen_structure(self) -> None:
        result = self._extract("잠실 한화 왕옌청 두산 곽빈 선발투수 예고")
        assessment = assess_material_event(
            result.events[0], facts={f.fact_id: f for f in result.facts},
            evidence={e.evidence_id: e for e in result.evidence},
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)
        self.assertEqual(assessment.reasons, (MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_NOMINAL_EVENT,))

    def test_normalized_noun_action_defers(self) -> None:
        result = self._extract("네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.")
        original = result.facts[0]
        normalized = EventFact(
            fact_id=original.fact_id, subject=original.subject, action="수주",
            object=original.object, evidence_ids=original.evidence_ids,
        )
        assessment = assess_material_event(
            result.events[0], facts={normalized.fact_id: normalized},
            evidence={e.evidence_id: e for e in result.evidence},
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertIsNone(assessment.selection_signal)
        self.assertEqual(assessment.reasons, (MaterialEventReason.PREDICATE_SIGNAL_MISSING,))

    def test_nonliteral_action_defers(self) -> None:
        result = self._extract("네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.")
        original = result.facts[0]
        unsupported = EventFact(
            fact_id=original.fact_id, subject=original.subject,
            action="수주를 성공적으로 완료했다", object=original.object,
            evidence_ids=original.evidence_ids,
        )
        assessment = assess_material_event(
            result.events[0], facts={unsupported.fact_id: unsupported},
            evidence={e.evidence_id: e for e in result.evidence},
        )
        self.assertEqual(assessment.reasons, (MaterialEventReason.FACT_FIELD_NOT_LITERAL,))

    def test_evidence_outside_event_defers(self) -> None:
        text = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
        result = self._extract(text)
        original = result.facts[0]
        foreign = EvidenceSpan(
            evidence_id="foreign-evidence", article_id="foreign-article", field=EvidenceField.BODY,
            start=0, end=len(text), text=text,
        )
        foreign_fact = EventFact(
            fact_id=original.fact_id, subject=original.subject, action=original.action,
            object=original.object, evidence_ids=(foreign.evidence_id,),
        )
        assessment = assess_material_event(
            result.events[0], facts={foreign_fact.fact_id: foreign_fact}, evidence={foreign.evidence_id: foreign},
        )
        self.assertEqual(assessment.reasons, (MaterialEventReason.EVIDENCE_OUTSIDE_EVENT,))

    def test_missing_fact_defers_item_locally(self) -> None:
        event = CandidateEvent(
            event_id="event-missing-fact", topic_id="ai_tech",
            fact_ids=("missing",), article_ids=("material-canary",),
        )
        assessment = assess_material_event(event, facts={}, evidence={})
        self.assertEqual(assessment.reasons, (MaterialEventReason.FACT_MISSING,))


if __name__ == "__main__":
    unittest.main()
