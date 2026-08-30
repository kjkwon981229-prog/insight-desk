from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from insight_desk.core import (
    CandidateEvent,
    ContractError,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.core.event_understanding_v2 import ArticleEventRole, UnderstandingStatus
from insight_desk.evidence_first_event_compilation_v1 import (
    ClaimCompleteness,
    canonical_draft_from_primary_claim,
    compile_article_evidence_first,
    compile_evidence_bound_claims,
    source_document_from_raw_article,
)
from insight_desk.semantic.pipeline import SemanticArticleResult


@dataclass(frozen=True)
class _Token:
    tag: str


class _FiniteMorphology:
    def analyze(self, _text: str):
        return (_Token("VV"), _Token("EF"))


class _AttributiveMorphology:
    def analyze(self, _text: str):
        return (_Token("VV"), _Token("ETM"), _Token("NNG"))


def _article(*, title: str, body: str, topic: str = "economy") -> RawArticle:
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    return RawArticle(
        article_id="article:experiment",
        provenance=SourceProvenance(
            source_id="source:experiment",
            source_name="fixture",
            url="https://fixture.invalid/evidence-first",
            retrieved_via="unit-test",
            fetched_at=now,
            published_at=now,
        ),
        title=title,
        body=body,
        topic_ids=(topic,),
    )


def _result(
    article: RawArticle,
    rows: list[tuple[str, str, str | None, str]],
    *,
    topic: str | None = None,
) -> SemanticArticleResult:
    evidence: list[EvidenceSpan] = []
    facts: list[EventFact] = []
    events: list[CandidateEvent] = []
    topic_id = topic or article.topic_ids[0]
    cursor = 0
    for index, (subject, action, object_text, sentence) in enumerate(rows):
        start = article.body.index(sentence, cursor)
        end = start + len(sentence)
        cursor = end
        evidence_id = f"ev:{index}"
        fact_id = f"fact:{index}"
        event_id = f"event:{index}"
        evidence.append(
            EvidenceSpan.from_article(
                evidence_id=evidence_id,
                article=article,
                field=EvidenceField.BODY,
                start=start,
                end=end,
            )
        )
        facts.append(
            EventFact(
                fact_id=fact_id,
                subject=subject,
                action=action,
                object=object_text,
                evidence_ids=(evidence_id,),
            )
        )
        events.append(
            CandidateEvent(
                event_id=event_id,
                topic_id=topic_id,
                fact_ids=(fact_id,),
                article_ids=(article.article_id,),
            )
        )
    return SemanticArticleResult(
        article_id=article.article_id,
        extractor_id="fixture-extractor",
        evidence=tuple(evidence),
        facts=tuple(facts),
        events=tuple(events),
    )


def test_background_status_claim_stays_non_primary_without_analytical_blacklist() -> None:
    first = "한국은행은 기준금리를 0.25%포인트 인상했다."
    second = "영끌족과 빚투 투자자의 부담이 가중되는 상황이다."
    article = _article(
        title="한국은행 기준금리 인상, 차주 부담 확대",
        body=f"{first} {second}",
    )
    result = _result(
        article,
        [
            ("한국은행", "기준금리를 0.25%포인트 인상했다", "기준금리", first),
            ("영끌족과 빚투 투자자", "부담이 가중되는 상황이다", "부담", second),
        ],
    )

    compilation = compile_article_evidence_first(
        article,
        result,
        morphology=_FiniteMorphology(),
    )

    assert compilation.status is UnderstandingStatus.RESOLVED
    assert compilation.primary_claim_id == "claim:event:0"
    assert compilation.assignment("claim:event:0").article_role is ArticleEventRole.PRIMARY
    assert compilation.assignment("claim:event:1").article_role is ArticleEventRole.SUPPORTING


def test_later_lineup_claim_does_not_beat_lead_event() -> None:
    first = "박준영은 감독의 신뢰 속 NC전에 선발 등판한다."
    second = "한화는 경기 전 선발 라인업을 발표했다."
    article = _article(
        title="박준영 선발, 감독 신뢰 속 NC전 출격",
        body=f"{first} {second}",
        topic="kbo_hanwha",
    )
    result = _result(
        article,
        [
            ("박준영", "감독의 신뢰 속 NC전에 선발 등판한다", None, first),
            ("한화", "경기 전 선발 라인업을 발표했다", "선발 라인업", second),
        ],
        topic="kbo_hanwha",
    )

    compilation = compile_article_evidence_first(
        article,
        result,
        morphology=_FiniteMorphology(),
    )

    assert compilation.primary_claim_id == "claim:event:0"
    assert compilation.assignment("claim:event:1").article_role is ArticleEventRole.SUPPORTING


def test_psat_claim_preserves_exact_change_semantics_without_introduction_rewrite() -> None:
    first = (
        "공직적격성평가(PSAT)는 내년부터 별도 검정시험 형태로 시행돼 "
        "국가공무원 5·7급 공채 등의 1차 시험을 대체한다."
    )
    second = "기존 5·7급 공개경쟁채용시험도 이미 공직적격성평가를 활용해 왔다."
    action = "내년부터 별도 검정시험 형태로 시행돼 국가공무원 5·7급 공채 등의 1차 시험을 대체한다"
    article = _article(
        title="내년부터 검정시험… 공직적격성평가 운영 방향 확정",
        body=f"{first} {second}",
        topic="psat_recruitment",
    )
    result = _result(
        article,
        [
            ("공직적격성평가(PSAT)", action, "국가공무원 5·7급 공채 등의 1차 시험", first),
            ("기존 5·7급 공개경쟁채용시험", "이미 공직적격성평가를 활용해 왔다", "공직적격성평가", second),
        ],
        topic="psat_recruitment",
    )

    compilation = compile_article_evidence_first(
        article,
        result,
        morphology=_FiniteMorphology(),
    )
    draft = canonical_draft_from_primary_claim(compilation)

    assert draft is not None
    assert draft.action == action
    assert "도입" not in draft.action
    assert draft.actor == "공직적격성평가(PSAT)"
    assert draft.object == "국가공무원 5·7급 공채 등의 1차 시험"


def test_canonical_boundary_accepts_only_selected_primary_claim() -> None:
    first = "앤트로픽은 로봇 제어용 하드웨어 표준을 공개했다."
    second = "에이전트는 실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다."
    article = _article(
        title="앤트로픽, 로봇 제어용 하드웨어 표준 공개",
        body=f"{first} {second}",
        topic="ai_tech",
    )
    result = _result(
        article,
        [
            ("앤트로픽", "로봇 제어용 하드웨어 표준을 공개했다", "로봇 제어용 하드웨어 표준", first),
            ("에이전트", "실제 로봇 등 물리적 장비를 안전하게 제어할 수 있다", "실제 로봇 등 물리적 장비", second),
        ],
        topic="ai_tech",
    )
    source = source_document_from_raw_article(article)

    compilation = compile_article_evidence_first(
        article,
        result,
        source=source,
        morphology=_FiniteMorphology(),
    )
    draft = canonical_draft_from_primary_claim(compilation)

    assert draft is not None
    assert draft.actor == "앤트로픽"
    assert all(ref.source_id == source.source_id for ref in draft.evidence_refs)
    for ref in draft.evidence_refs:
        ref.validate_against(source)
    assert compilation.assignment("claim:event:1").article_role is ArticleEventRole.SUPPORTING


def test_deep_claim_without_lead_or_title_binding_abstains() -> None:
    lead = "이번 보고서는 여러 현황을 정리했다."
    second = "기관은 별도 운영안을 확정했다."
    article = _article(
        title="정기 현황 보고서",
        body=f"{lead} {second}",
    )
    result = _result(
        article,
        [("기관", "별도 운영안을 확정했다", "별도 운영안", second)],
    )

    compilation = compile_article_evidence_first(
        article,
        result,
        morphology=_FiniteMorphology(),
    )

    assert compilation.status is UnderstandingStatus.UNRESOLVED
    assert compilation.primary_claim_id is None
    assert canonical_draft_from_primary_claim(compilation) is None
    assert "article_centrality_unresolved" in compilation.uncertainty_reasons


def test_incomplete_predicate_is_explicit_unresolved_claim_not_drop() -> None:
    sentence = "지원하는 기업 계획."
    article = _article(title="기업 계획", body=sentence)
    result = _result(
        article,
        [("기업", "지원하는 기업 계획", None, sentence)],
    )

    claims = compile_evidence_bound_claims(
        article,
        result,
        morphology=_AttributiveMorphology(),
    )
    compilation = compile_article_evidence_first(
        article,
        result,
        morphology=_AttributiveMorphology(),
    )

    assert len(claims) == 1
    assert claims[0].completeness is ClaimCompleteness.UNRESOLVED
    assert claims[0].uncertainty_reasons == ("predicate_incomplete",)
    assert compilation.status is UnderstandingStatus.UNRESOLVED
    assert compilation.primary_claim_id is None


def test_nonliteral_semantic_field_is_rejected_before_claim_contract() -> None:
    sentence = "한국은행은 기준금리를 인상했다."
    article = _article(title="한국은행 기준금리 인상", body=sentence)
    result = _result(
        article,
        [("한국은행", "기준금리를 동결했다", "기준금리", sentence)],
    )

    with pytest.raises(ContractError, match="not literal"):
        compile_evidence_bound_claims(
            article,
            result,
            morphology=_FiniteMorphology(),
        )
