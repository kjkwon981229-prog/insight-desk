from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from insight_desk.core import (
    ArticleEventRole,
    CandidateEvent,
    CanonicalEvent,
    CanonicalEvidenceRef,
    Certainty,
    ContractError,
    EventFact,
    EvidenceField,
    EvidenceSpan,
    RawArticle,
    SelectionVerdict,
    SourceDocument,
    SourceProvenance,
    UnderstandingStatus,
)
from insight_desk.generation import GenerationContractError, GenerationRequest
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase7_v2 import (
    build_canonical_generation_request,
)
from insight_desk.production_runtime_v2 import production_v2_runtime
from insight_desk.semantic import build_resilient_fact_extractor
from insight_desk.semantic.events import Phase6SelectionContext
from insight_desk.semantic.material import MaterialEventVerdict
from insight_desk.verification_pipeline import DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID
from scripts import phase11_daily_production_core as production_core

ROOT = Path(__file__).resolve().parents[1]
V6_QUALIFICATION = ROOT / "tests" / "fixtures" / "event_understanding_qualification_v6.json"
SEMANTIC_RUNTIME_AVAILABLE = importlib.util.find_spec("kiwipiepy") is not None


@dataclass(frozen=True, slots=True)
class _ArticleCase:
    case_id: str
    topic: str
    title: str
    body: str
    expected_proposition: str | None
    article_id: str | None = None
    source_name: str = "source-grounded production contract"
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class _Outcome:
    case_id: str
    proposition: str | None
    exact_provenance: bool
    verifier_ids: tuple[str, ...]

    @property
    def published(self) -> bool:
        return self.proposition is not None


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _v6_source_cases(qualification: dict[str, object]):
    source_cases: dict[str, tuple[dict[str, object], datetime]] = {}
    source_fixtures = qualification.get("source_fixtures")
    if not isinstance(source_fixtures, list):
        raise AssertionError("V6 source fixtures are missing")
    for relative in source_fixtures:
        fixture = json.loads((ROOT / str(relative)).read_text(encoding="utf-8"))
        clock = datetime.fromisoformat(str(fixture["replay_clock"]))
        for raw in fixture["cases"]:
            source_cases[str(raw["case_id"])] = (raw, clock)
    return source_cases


def _run_cases(
    cases: tuple[_ArticleCase, ...],
    *,
    clocks: dict[str, datetime] | None = None,
) -> dict[str, _Outcome]:
    default_clock = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
    outcomes: dict[str, _Outcome] = {}
    with production_v2_runtime(production_core) as registry:
        topics = {
            topic.topic_id: topic
            for topic in production_core.load_topics(ROOT / "config" / "topics.json")
        }
        semantic = production_core.SemanticPipeline()
        extractor = build_resilient_fact_extractor()
        phase6 = production_core.Phase6EventEngine()
        for case in cases:
            clock = (clocks or {}).get(case.case_id, default_clock)
            article_id = case.article_id or f"production-contract:{case.case_id}"
            article = RawArticle(
                article_id=article_id,
                provenance=SourceProvenance(
                    source_id=f"production-contract-provenance:{case.case_id}",
                    source_name=case.source_name,
                    url=(
                        case.source_url
                        or f"https://example.com/source-grounded/{case.case_id}"
                    ),
                    retrieved_via="frozen-production-contract",
                    fetched_at=clock,
                    published_at=clock,
                ),
                title=case.title,
                body=case.body,
                topic_ids=(case.topic,),
            )
            topic = topics[case.topic]
            result = semantic.extract_article(
                article,
                topic_id=case.topic,
                extractor=extractor,
            )
            facts = {fact.fact_id: fact for fact in result.facts}
            evidence = {span.evidence_id: span for span in result.evidence}
            primary = []
            for event in result.events:
                event_relevant = production_core.event_topic_relevant(
                    event=event,
                    facts=facts,
                    evidence=evidence,
                    topic=topic,
                )
                decision = production_core.event_understanding_decision(
                    event,
                    facts=facts,
                    evidence=evidence,
                    morphology=None,
                    now=clock,
                )
                if (
                    decision.status is UnderstandingStatus.RESOLVED
                    and decision.article_role is ArticleEventRole.PRIMARY
                    and decision.publishable_event
                    and event_relevant
                ):
                    primary.append(event)

            if len(primary) != 1:
                outcomes[case.case_id] = _Outcome(case.case_id, None, False, ())
                continue

            event = primary[0]
            canonical = registry.canonical_event(event.event_id)
            source = registry.source_for_event(event.event_id)
            assessment = phase6.assess_with_auto_material(
                event,
                facts=facts,
                evidence=evidence,
                selection_context=Phase6SelectionContext(
                    topic_relevant=True,
                    fresh=True,
                    source_usable=True,
                    identity_resolved=True,
                ),
            )
            if (
                assessment.material.verdict is not MaterialEventVerdict.MATERIAL
                or assessment.event_assessment.selection.verdict is not SelectionVerdict.INCLUDE
            ):
                outcomes[case.case_id] = _Outcome(case.case_id, None, False, ())
                continue
            candidate = production_core.produce_phase7_entry_candidate(
                GenerationRequest(event=event, facts=facts, evidence=evidence)
            )
            if candidate is None or not candidate.publishable:
                outcomes[case.case_id] = _Outcome(case.case_id, None, False, ())
                continue

            exact_ranges = []
            for ref in canonical.evidence_refs:
                ref.validate_against(source)
                source_text = source.title if ref.field == "title" else source.body
                exact_ranges.append(source_text[ref.start : ref.end])
            draft = candidate.final_generation.draft
            exact = (
                len(exact_ranges) == 1
                and draft.headline == exact_ranges[0]
                and draft.summary == exact_ranges[0]
            )
            verifier_ids = tuple(
                check.verifier_id
                for claim in candidate.verification.claims
                for check in claim.claim.checks
            )
            outcomes[case.case_id] = _Outcome(
                case.case_id,
                draft.headline,
                exact,
                verifier_ids,
            )
    return outcomes


@unittest.skipUnless(
    SEMANTIC_RUNTIME_AVAILABLE,
    "source-grounded production stability requires the production semantic-local runtime",
)
class SourceGroundedProductionStabilityTests(unittest.TestCase):
    def test_frozen_v6_runs_through_current_production_authority(self) -> None:
        qualification = json.loads(V6_QUALIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(qualification["schema_version"], 6)
        source_cases = _v6_source_cases(qualification)
        expected_cases = tuple(qualification["cases"])
        cases = []
        clocks: dict[str, datetime] = {}
        for expected in expected_cases:
            case_id = str(expected["case_id"])
            raw, clock = source_cases[case_id]
            cases.append(
                _ArticleCase(
                    case_id=case_id,
                    topic=str(raw["topic_id"]),
                    title=str(raw["search_title"]),
                    body=str(raw["source_excerpt"]),
                    expected_proposition=None,
                    article_id=str(raw["candidate_id"]),
                    source_name=str(raw["source_name"]),
                    source_url=str(raw["source_url"]),
                )
            )
            clocks[case_id] = clock

        outcomes = _run_cases(tuple(cases), clocks=clocks)
        historical_ids = {
            "run413-bok-kbs-rate-decision",
            "run413-bok-kmib-outlook-child",
            "run413-kpop-alphadriveone-actor-preserved",
            "run413-kbo-osen-same-game-source",
        }
        for expected in expected_cases:
            case_id = str(expected["case_id"])
            with self.subTest(case_id=case_id):
                outcome = outcomes[case_id]
                self.assertTrue(outcome.published)
                self.assertTrue(outcome.exact_provenance)
                self.assertEqual(
                    set(outcome.verifier_ids),
                    {DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID},
                )
                assert outcome.proposition is not None
                self.assertFalse(
                    any(
                        literal in outcome.proposition
                        for literal in _strings(expected.get("context_evidence_literals"))
                    )
                )
                if expected.get("manual_semantic_review_required") is True:
                    self.assertIn("검정시험 형태로 처음 시행", outcome.proposition)
                    self.assertIn("1차 시험으로 대체", outcome.proposition)
                    self.assertNotIn("PSAT 도입", outcome.proposition)
                    continue
                groups = tuple(
                    group
                    for group in expected.get("expected_events", [])
                    if isinstance(group, dict)
                )
                self.assertTrue(
                    any(
                        all(
                            literal in outcome.proposition
                            for literal in _strings(group.get("required_evidence_literals"))
                        )
                        and all(
                            literal in outcome.proposition
                            for literal in _strings(group.get("required_entity_literals"))
                        )
                        for group in groups
                    )
                )

        self.assertEqual(sum(outcomes[case_id].published for case_id in historical_ids), 4)

    def test_adversarial_cases_publish_or_abstain_without_false_publication(self) -> None:
        cases = (
            _ArticleCase(
                "same-actor-central-and-background",
                "ai_tech",
                "오로라연구소, AI 기술 기반 양자센서 시제품 공개",
                "오로라연구소는 AI 기술 기반 양자센서 시제품을 공개했다. "
                "오로라연구소는 2024년부터 관련 연구를 진행해 왔다.",
                "오로라연구소는 AI 기술 기반 양자센서 시제품을 공개했다.",
            ),
            _ArticleCase(
                "background-before-central-event",
                "ai_tech",
                "네오랩, 저전력 반도체 공개",
                "네오랩은 2024년부터 저전력 반도체를 연구해 왔다. "
                "네오랩은 30일 저전력 반도체 시제품을 공개했다.",
                None,
            ),
            _ArticleCase(
                "headline-body-centrality-conflict",
                "ai_tech",
                "세림연구원, AI 기술 기반 우주망원경 개발 경험",
                "다온우주원은 30일 새 AI 기술 기반 위성 관측 장비를 공개했다. "
                "세림연구원은 2023년 AI 기술 기반 우주망원경을 개발했다.",
                None,
            ),
            _ArticleCase(
                "coordinated-actors",
                "ai_tech",
                "한빛연구소·새론대, 공동 AI 모델 공개",
                "한빛연구소와 새론대학교는 30일 공동 AI 모델을 공개했다.",
                "한빛연구소와 새론대학교는 30일 공동 AI 모델을 공개했다.",
            ),
            _ArticleCase(
                "substantive-embedded-clause",
                "psat_recruitment",
                "별도 자격시험 시행안 확정",
                "내년부터 별도 자격시험 형태로 시행돼 기존 국가공무원 채용시험의 1차 시험을 "
                "대체하는 평가제도의 운영안이 확정됐다.",
                "내년부터 별도 자격시험 형태로 시행돼 기존 국가공무원 채용시험의 1차 시험을 "
                "대체하는 평가제도의 운영안이 확정됐다.",
            ),
            _ArticleCase(
                "quotation-and-reporter-event-conflict",
                "ai_tech",
                "미래로봇, 물류 로봇 시제품 공개",
                "미래로봇 대표는 ‘내년에 상용화할 계획’이라고 말했다. "
                "미래로봇은 30일 물류 로봇 시제품을 공개했다.",
                None,
            ),
            _ArticleCase(
                "planned-and-completed-status-conflict",
                "economy",
                "푸른에너지, 투자 실증사업 완료",
                "푸른에너지는 내년 3월 2단계 투자사업을 시작할 예정이다. "
                "푸른에너지는 30일 1단계 투자 실증사업을 완료했다.",
                None,
            ),
            _ArticleCase(
                "historical-comparison",
                "economy",
                "새봄은행, 금융당국 허가 후 간편결제 서비스 출시",
                "새봄은행은 금융당국 허가를 받아 30일 간편결제 서비스를 출시했다. "
                "새봄은행은 2025년 8월 20일 모바일 통장을 출시했다.",
                "새봄은행은 금융당국 허가를 받아 30일 간편결제 서비스를 출시했다.",
            ),
            _ArticleCase(
                "two-events-one-source-proposition",
                "ai_tech",
                "하늘연구원, AI 기술 기반 기상 센서 공개·시험 착수",
                "하늘연구원은 30일 AI 기술 기반 기상 센서를 공개하고 제주에서 현장 시험에 착수했다.",
                "하늘연구원은 30일 AI 기술 기반 기상 센서를 공개하고 제주에서 현장 시험에 착수했다.",
            ),
            _ArticleCase(
                "high-cardinality-article",
                "ai_tech",
                "새빛연구소, AI 반도체 시제품 공개",
                "새빛연구소는 AI 반도체 시제품을 공개했다. "
                "새빛연구소는 연구 인력을 확대했다. "
                "협력사는 생산 설비를 점검했다. "
                "시험기관은 성능 자료를 발표했다. "
                "투자사는 신규 펀드를 조성했다. "
                "대학 연구팀은 후속 논문을 제출했다. "
                "부품사는 공급 계약을 체결했다. "
                "지역 기관은 지원 센터를 개소했다. "
                "운영사는 교육 과정을 시작했다. "
                "위원회는 다음 회의 일정을 확정했다.",
                "새빛연구소는 AI 반도체 시제품을 공개했다.",
            ),
            _ArticleCase(
                "topic-context-outside-central-proposition",
                "kpop",
                "새봄시, 국제정원박람회 운영 계획 공개",
                "새봄시는 국제정원박람회 운영 계획을 공개했다. "
                "행사장에서는 가수 공연과 K-POP 댄스 무대도 운영한다.",
                None,
            ),
        )
        outcomes = _run_cases(cases)
        correctly_published = 0
        correctly_abstained = 0
        for case in cases:
            with self.subTest(case_id=case.case_id):
                outcome = outcomes[case.case_id]
                if case.expected_proposition is None:
                    self.assertFalse(outcome.published)
                    correctly_abstained += 1
                    continue
                self.assertEqual(outcome.proposition, case.expected_proposition)
                self.assertTrue(outcome.exact_provenance)
                self.assertEqual(
                    set(outcome.verifier_ids),
                    {DETERMINISTIC_SOURCE_PROOF_VERIFIER_ID},
                )
                correctly_published += 1
        self.assertEqual(correctly_published, 6)
        self.assertEqual(correctly_abstained, 5)

    def test_multiple_canonical_evidence_spans_abstain(self) -> None:
        first = "한빛연구소는 공동 모델을 공개했다."
        second = "새론대학교는 평가 자료를 발표했다."
        body = first + " " + second
        now = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
        source = SourceDocument(
            source_id="source:multi-ref",
            candidate_ids=("article:multi-ref",),
            publisher="fixture",
            url="https://example.com/source-grounded/multi-ref",
            title="공동 모델 공개",
            body=body,
            fetched_at=now,
            publication_time=now,
            retrieved_via="frozen-production-contract",
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )
        second_start = len(first) + 1
        spans = (
            EvidenceSpan(
                evidence_id="evidence:first",
                article_id="article:multi-ref",
                field=EvidenceField.BODY,
                start=0,
                end=len(first),
                text=first,
            ),
            EvidenceSpan(
                evidence_id="evidence:second",
                article_id="article:multi-ref",
                field=EvidenceField.BODY,
                start=second_start,
                end=len(body),
                text=second,
            ),
        )
        fact = EventFact(
            fact_id="fact:multi-ref",
            subject="한빛연구소",
            action="공동 모델을 공개했다",
            evidence_ids=tuple(span.evidence_id for span in spans),
            certainty=Certainty.ASSERTED,
        )
        candidate = CandidateEvent(
            event_id="event:multi-ref",
            topic_id="ai_tech",
            fact_ids=(fact.fact_id,),
            article_ids=("article:multi-ref",),
        )
        refs = tuple(
            CanonicalEvidenceRef(
                source_id=source.source_id,
                field="body",
                start=span.start,
                end=span.end,
                text_sha256=hashlib.sha256(span.text.encode("utf-8")).hexdigest(),
            )
            for span in spans
        )
        canonical = CanonicalEvent(
            event_id=candidate.event_id,
            topic=candidate.topic_id,
            actor=fact.subject,
            action=fact.action,
            event_type="news_event",
            source_ids=(source.source_id,),
            fact_ids=(fact.fact_id,),
            evidence_ids=tuple(span.evidence_id for span in spans),
            evidence_refs=refs,
            certainty=Certainty.ASSERTED,
        )
        registry = ProductionV2Registry(
            sources_by_article={"article:multi-ref": source},
            events_by_id={canonical.event_id: canonical},
        )
        with self.assertRaisesRegex(
            GenerationContractError,
            "requires one exact proposition",
        ):
            build_canonical_generation_request(
                registry,
                GenerationRequest(
                    event=candidate,
                    facts={fact.fact_id: fact},
                    evidence={span.evidence_id: span for span in spans},
                ),
            )

    def test_source_document_rejects_a_body_digest_from_different_bytes(self) -> None:
        body = "원문 본문이다."
        now = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
        with self.assertRaisesRegex(ContractError, "differs from SourceDocument body bytes"):
            SourceDocument(
                source_id="source:tampered",
                candidate_ids=("article:tampered",),
                publisher="fixture",
                url="https://example.com/source-grounded/tampered",
                title="원문 제목",
                body=body,
                fetched_at=now,
                publication_time=now,
                retrieved_via="frozen-production-contract",
                content_sha256=hashlib.sha256("다른 본문".encode()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
