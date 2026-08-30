from __future__ import annotations

"""Bounded evidence-first Event Understanding experiment.

This module is intentionally isolated from production wiring.  It tests one structural hypothesis:
exact source evidence should become explicit claim objects *before* article centrality and before any
CanonicalEventDraft exists.

The experiment does not contain topic vocabularies, analytical-predicate blacklists, provider
prompts, generated-text judgments, or publication policy.  It consumes the current deterministic
semantic extractor only as evidence preparation.
"""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
from typing import Mapping, Protocol

from insight_desk.core import (
    CandidateEvent,
    ContractError,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceDocument,
)
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    CanonicalEventDraft,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)
from insight_desk.event_predicate_v2 import PredicateCompleteness, assess_event_predicate
from insight_desk.semantic.pipeline import SemanticArticleResult


class MorphologyPort(Protocol):
    def analyze(self, text: str): ...


class ClaimCompleteness(StrEnum):
    COMPLETE = "complete"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EvidenceBoundClaim:
    """One source-surface claim before article-level centrality.

    ``actor`` / ``action`` / ``object`` are copied from the deterministic fact helper, but this
    contract independently proves that those fields are literal substrings of the exact cited
    source span.  A claim therefore cannot exist merely because an EventFact object exists.
    """

    claim_id: str
    topic: str
    article_id: str
    fact_id: str
    actor: str
    action: str
    evidence_ids: tuple[str, ...]
    evidence_refs: tuple[UnderstandingEvidenceRef, ...]
    completeness: ClaimCompleteness
    object: str | None = None
    event_time: str | None = None
    participants: tuple[str, ...] = ()
    temporal_state: object | None = None
    certainty: object | None = None
    polarity: object | None = None
    location: str | None = None
    cause: str | None = None
    uncertainty_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("claim_id", self.claim_id),
            ("topic", self.topic),
            ("article_id", self.article_id),
            ("fact_id", self.fact_id),
            ("actor", self.actor),
            ("action", self.action),
        ):
            if not str(value).strip():
                raise ContractError(f"{name} must be non-empty")
        if not self.evidence_ids or len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ContractError("evidence-first claim requires unique evidence ids")
        if not self.evidence_refs or len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ContractError("evidence-first claim requires unique exact evidence refs")
        if self.object is not None and not self.object.strip():
            raise ContractError("claim object must be non-empty when present")
        if self.completeness is ClaimCompleteness.COMPLETE and self.uncertainty_reasons:
            raise ContractError("complete evidence-first claim cannot carry uncertainty reasons")
        if self.completeness is ClaimCompleteness.UNRESOLVED and not self.uncertainty_reasons:
            raise ContractError("unresolved evidence-first claim requires uncertainty reasons")


@dataclass(frozen=True, slots=True)
class ClaimAssignment:
    claim_id: str
    article_role: ArticleEventRole
    topic_relation: TopicRelation
    understanding_status: UnderstandingStatus
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArticleClaimCompilation:
    """Evidence-first article result.

    All source-bound claims remain visible in this intermediate result.  Exactly one claim may be
    PRIMARY.  Only that claim is eligible to cross the CanonicalEventDraft boundary.
    """

    article_id: str
    topic: str
    claims: tuple[EvidenceBoundClaim, ...]
    assignments: tuple[ClaimAssignment, ...]
    status: UnderstandingStatus
    primary_claim_id: str | None = None
    uncertainty_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise ContractError("evidence-first compilation claim ids must be unique")
        assignment_ids = tuple(item.claim_id for item in self.assignments)
        if set(assignment_ids) != set(claim_ids) or len(assignment_ids) != len(claim_ids):
            raise ContractError("every evidence-first claim requires exactly one assignment")
        primary = [
            item.claim_id
            for item in self.assignments
            if item.article_role is ArticleEventRole.PRIMARY
            and item.understanding_status is UnderstandingStatus.RESOLVED
        ]
        if len(primary) > 1:
            raise ContractError("evidence-first compilation permits at most one primary claim")
        if self.primary_claim_id is not None and primary != [self.primary_claim_id]:
            raise ContractError("primary_claim_id differs from primary assignment")
        if self.status is UnderstandingStatus.RESOLVED:
            if self.primary_claim_id is None or self.uncertainty_reasons:
                raise ContractError("resolved evidence-first article requires one primary claim")
        elif not self.uncertainty_reasons:
            raise ContractError("unresolved evidence-first article requires uncertainty reasons")

    def assignment(self, claim_id: str) -> ClaimAssignment:
        for item in self.assignments:
            if item.claim_id == claim_id:
                return item
        raise ContractError(f"missing claim assignment: {claim_id}")

    def primary_claim(self) -> EvidenceBoundClaim | None:
        if self.primary_claim_id is None:
            return None
        for claim in self.claims:
            if claim.claim_id == self.primary_claim_id:
                return claim
        raise ContractError("primary claim id is outside compilation claims")


def source_document_from_raw_article(article: RawArticle) -> SourceDocument:
    """Bind exact article bytes for the experiment without touching production registries."""

    return SourceDocument(
        source_id=f"experiment-source:{article.article_id}",
        candidate_ids=(article.article_id,),
        publisher=article.provenance.source_name,
        url=article.provenance.url,
        title=article.title,
        body=article.body,
        fetched_at=article.provenance.fetched_at,
        publication_time=article.provenance.published_at,
        retrieved_via=article.provenance.retrieved_via,
        content_sha256=hashlib.sha256(article.body.encode("utf-8")).hexdigest(),
    )


def _evidence_ref(source: SourceDocument, span: EvidenceSpan) -> UnderstandingEvidenceRef:
    field = (
        UnderstandingEvidenceField.TITLE
        if span.field is EvidenceField.TITLE
        else UnderstandingEvidenceField.BODY
    )
    return UnderstandingEvidenceRef.from_source(
        source,
        field=field,
        start=span.start,
        end=span.end,
    )


def _fields_are_literal(fact: EventFact, spans: tuple[EvidenceSpan, ...]) -> bool:
    texts = tuple(span.text for span in spans)
    required = (fact.subject, fact.action) + ((fact.object,) if fact.object is not None else ())
    return all(any(value in text for text in texts) for value in required)


def _predicate_completeness(action: str, morphology: MorphologyPort | None) -> ClaimCompleteness:
    # The production deterministic extractor already requires a verbal predicate.  When morphology
    # is available, the experiment additionally applies the shared structural predicate owner; it
    # does not add a second vocabulary of semantic event types.
    if morphology is None:
        return ClaimCompleteness.COMPLETE
    assessment = assess_event_predicate(action, morphology=morphology)
    if assessment.completeness is PredicateCompleteness.COMPLETE:
        return ClaimCompleteness.COMPLETE
    return ClaimCompleteness.UNRESOLVED


def compile_evidence_bound_claims(
    article: RawArticle,
    result: SemanticArticleResult,
    *,
    source: SourceDocument | None = None,
    morphology: MorphologyPort | None = None,
) -> tuple[EvidenceBoundClaim, ...]:
    """Compile current extractor output into first-class exact-evidence claims.

    This function intentionally ignores any pre-existing event-centrality decision. CandidateEvent
    is used only to locate the fact/article relationship emitted by the deterministic helper.
    """

    if result.article_id != article.article_id:
        raise ContractError("semantic result belongs to a different article")
    source = source or source_document_from_raw_article(article)
    if source.title != article.title or source.body != article.body:
        raise ContractError("experiment SourceDocument bytes differ from RawArticle")

    facts: Mapping[str, EventFact] = {fact.fact_id: fact for fact in result.facts}
    evidence: Mapping[str, EvidenceSpan] = {span.evidence_id: span for span in result.evidence}
    claims: list[EvidenceBoundClaim] = []

    for event in result.events:
        if event.article_ids != (article.article_id,) or len(event.fact_ids) != 1:
            # A multi-source or multi-fact event is already an identity-level structure and is not a
            # valid evidence-first claim input.  The experiment does not guess how to split it.
            continue
        fact = facts.get(event.fact_ids[0])
        if fact is None:
            continue
        spans: list[EvidenceSpan] = []
        for evidence_id in fact.evidence_ids:
            span = evidence.get(evidence_id)
            if span is None or span.article_id != article.article_id:
                raise ContractError(f"{fact.fact_id}: claim evidence is missing or non-local")
            span.validate_against(article)
            spans.append(span)
        frozen_spans = tuple(spans)
        if not _fields_are_literal(fact, frozen_spans):
            raise ContractError(f"{fact.fact_id}: claim semantic fields are not literal in evidence")

        completeness = _predicate_completeness(fact.action, morphology)
        reasons: tuple[str, ...] = ()
        if completeness is ClaimCompleteness.UNRESOLVED:
            reasons = ("predicate_incomplete",)
        claims.append(
            EvidenceBoundClaim(
                claim_id=f"claim:{event.event_id}",
                topic=event.topic_id,
                article_id=article.article_id,
                fact_id=fact.fact_id,
                actor=fact.subject,
                action=fact.action,
                object=fact.object,
                evidence_ids=fact.evidence_ids,
                evidence_refs=tuple(_evidence_ref(source, span) for span in frozen_spans),
                completeness=completeness,
                event_time=fact.event_date,
                participants=fact.participants,
                temporal_state=fact.temporal_state,
                certainty=fact.certainty,
                polarity=fact.polarity,
                location=fact.location,
                cause=fact.cause,
                uncertainty_reasons=reasons,
            )
        )

    return tuple(claims)


def _first_sentence_end(body: str) -> int:
    positions = [index + 1 for index, char in enumerate(body) if char in ".!?…\n"]
    return min(positions) if positions else len(body)


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _title_bound(article: RawArticle, value: str | None) -> int:
    if value is None:
        return 0
    needle = _normalized(value)
    return int(bool(needle) and needle in _normalized(article.title))


def _claim_body_start(claim: EvidenceBoundClaim) -> int:
    body_starts = [
        ref.start
        for ref in claim.evidence_refs
        if ref.field is UnderstandingEvidenceField.BODY
    ]
    return min(body_starts) if body_starts else 2**31 - 1


def _claim_has_title_evidence(claim: EvidenceBoundClaim) -> int:
    return int(any(ref.field is UnderstandingEvidenceField.TITLE for ref in claim.evidence_refs))


def _centrality_rank(
    article: RawArticle,
    claim: EvidenceBoundClaim,
    *,
    lead_end: int,
) -> tuple[int, int, int, int, int]:
    start = _claim_body_start(claim)
    lead_bound = int(start < lead_end)
    actor_title_bound = _title_bound(article, claim.actor)
    object_title_bound = _title_bound(article, claim.object)
    title_evidence = _claim_has_title_evidence(claim)
    # Source discourse is the primary signal.  Title binding is only a bounded rescue when the
    # extractor fails to surface a complete lead claim.  No event/industry vocabulary participates.
    return (lead_bound, actor_title_bound, object_title_bound, title_evidence, -start)


def select_claim_centrality(
    article: RawArticle,
    claims: tuple[EvidenceBoundClaim, ...],
) -> ArticleClaimCompilation:
    """Select one primary claim using only exact-source discourse structure.

    Non-primary complete claims remain SUPPORTING+DIRECT.  The experiment deliberately avoids
    pretending that it semantically knows whether a secondary complete claim is "background" or an
    independent supporting event; the only publication-relevant assertion is that it is not the
    source-central claim.
    """

    if not claims:
        return ArticleClaimCompilation(
            article_id=article.article_id,
            topic=article.topic_ids[0] if article.topic_ids else "unknown",
            claims=(),
            assignments=(),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("no_evidence_bound_claims",),
        )

    topics = {claim.topic for claim in claims}
    if len(topics) != 1:
        raise ContractError("evidence-first article claims must share one topic")
    topic = next(iter(topics))
    complete = tuple(claim for claim in claims if claim.completeness is ClaimCompleteness.COMPLETE)
    if not complete:
        assignments = tuple(
            ClaimAssignment(
                claim_id=claim.claim_id,
                article_role=ArticleEventRole.CONTEXT,
                topic_relation=TopicRelation.UNRESOLVED,
                understanding_status=UnderstandingStatus.UNRESOLVED,
                reasons=claim.uncertainty_reasons,
            )
            for claim in claims
        )
        return ArticleClaimCompilation(
            article_id=article.article_id,
            topic=topic,
            claims=claims,
            assignments=assignments,
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("no_complete_claim",),
        )

    lead_end = _first_sentence_end(article.body)
    ranked = sorted(
        complete,
        key=lambda claim: _centrality_rank(article, claim, lead_end=lead_end),
        reverse=True,
    )
    winner = ranked[0]
    winner_rank = _centrality_rank(article, winner, lead_end=lead_end)
    lead_bound, actor_title_bound, _object_title_bound, title_evidence, _ = winner_rank
    centrality_proven = bool(lead_bound or actor_title_bound or title_evidence)

    assignments: list[ClaimAssignment] = []
    if not centrality_proven:
        for claim in claims:
            if claim.completeness is ClaimCompleteness.COMPLETE:
                assignments.append(
                    ClaimAssignment(
                        claim_id=claim.claim_id,
                        article_role=ArticleEventRole.SUPPORTING,
                        topic_relation=TopicRelation.UNRESOLVED,
                        understanding_status=UnderstandingStatus.UNRESOLVED,
                        reasons=("article_centrality_unresolved",),
                    )
                )
            else:
                assignments.append(
                    ClaimAssignment(
                        claim_id=claim.claim_id,
                        article_role=ArticleEventRole.CONTEXT,
                        topic_relation=TopicRelation.UNRESOLVED,
                        understanding_status=UnderstandingStatus.UNRESOLVED,
                        reasons=claim.uncertainty_reasons,
                    )
                )
        return ArticleClaimCompilation(
            article_id=article.article_id,
            topic=topic,
            claims=claims,
            assignments=tuple(assignments),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("article_centrality_unresolved",),
        )

    for claim in claims:
        if claim.claim_id == winner.claim_id:
            assignments.append(
                ClaimAssignment(
                    claim_id=claim.claim_id,
                    article_role=ArticleEventRole.PRIMARY,
                    topic_relation=TopicRelation.DIRECT,
                    understanding_status=UnderstandingStatus.RESOLVED,
                )
            )
        elif claim.completeness is ClaimCompleteness.COMPLETE:
            assignments.append(
                ClaimAssignment(
                    claim_id=claim.claim_id,
                    article_role=ArticleEventRole.SUPPORTING,
                    topic_relation=TopicRelation.DIRECT,
                    understanding_status=UnderstandingStatus.RESOLVED,
                    reasons=("non_primary_complete_claim",),
                )
            )
        else:
            assignments.append(
                ClaimAssignment(
                    claim_id=claim.claim_id,
                    article_role=ArticleEventRole.CONTEXT,
                    topic_relation=TopicRelation.UNRESOLVED,
                    understanding_status=UnderstandingStatus.UNRESOLVED,
                    reasons=claim.uncertainty_reasons,
                )
            )

    return ArticleClaimCompilation(
        article_id=article.article_id,
        topic=topic,
        claims=claims,
        assignments=tuple(assignments),
        status=UnderstandingStatus.RESOLVED,
        primary_claim_id=winner.claim_id,
    )


def compile_article_evidence_first(
    article: RawArticle,
    result: SemanticArticleResult,
    *,
    source: SourceDocument | None = None,
    morphology: MorphologyPort | None = None,
) -> ArticleClaimCompilation:
    claims = compile_evidence_bound_claims(
        article,
        result,
        source=source,
        morphology=morphology,
    )
    return select_claim_centrality(article, claims)


def canonical_draft_from_primary_claim(
    compilation: ArticleClaimCompilation,
    *,
    event_type: str = "news_event",
) -> CanonicalEventDraft | None:
    """Cross the canonical boundary only after evidence-first centrality is resolved."""

    claim = compilation.primary_claim()
    if claim is None or compilation.status is not UnderstandingStatus.RESOLVED:
        return None
    assignment = compilation.assignment(claim.claim_id)
    if assignment.article_role is not ArticleEventRole.PRIMARY:
        raise ContractError("only a primary evidence-first claim may become CanonicalEventDraft")
    return CanonicalEventDraft(
        draft_id=f"evidence-first:{claim.claim_id}",
        topic=claim.topic,
        actor=claim.actor,
        action=claim.action,
        object=claim.object,
        event_type=event_type,
        source_ids=tuple(dict.fromkeys(ref.source_id for ref in claim.evidence_refs)),
        evidence_refs=claim.evidence_refs,
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        understanding_status=UnderstandingStatus.RESOLVED,
        event_time=claim.event_time,
        participants=claim.participants,
        temporal_state=claim.temporal_state,
        certainty=claim.certainty,
        polarity=claim.polarity,
        location=claim.location,
        cause=claim.cause,
    )
