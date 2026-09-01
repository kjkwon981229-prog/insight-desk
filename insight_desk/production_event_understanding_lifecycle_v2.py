from __future__ import annotations

"""Single-owner production lifecycle for Event Understanding.

The legacy deterministic extractor remains an evidence helper while semantic-provider qualification
is pending. It is not allowed to create CanonicalEvent objects. This boundary executes article-level
Event Understanding once, promotes only resolved primary events through CanonicalEventDraft, and
runs authoritative enrichment only after that promotion. The same owner also interprets bounded
identity-resolution bridge sources without registering them for publication.
"""

from datetime import date
from types import ModuleType
from typing import Mapping

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    ContractError,
    EvidenceField,
    EvidenceSpan,
    EventFact,
)
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    CanonicalEventDraft,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
    canonical_event_from_draft,
)
from insight_desk.production_event_understanding_compat_v2 import (
    CompatibilityEventUnderstandingDecision,
    assess_compatibility_article_understanding,
)
from insight_desk.production_orchestrator_compat_v2 import (
    ProductionV2Registry,
    source_document_from_article,
)
from insight_desk.semantic.pipeline import (
    SemanticArticleResult,
    SemanticPipeline as LegacySemanticPipeline,
)
from insight_desk.semantic.tooling import KiwiMorphologyHelper


def _optional_morphology():
    try:
        return KiwiMorphologyHelper()
    except RuntimeError:
        return None


def _event_time(value: str | None) -> str | None:
    """Carry only already-resolved ISO dates; never infer a temporal value."""

    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _understanding_evidence_refs(
    *,
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
    source,
) -> tuple[UnderstandingEvidenceRef, ...]:
    refs: list[UnderstandingEvidenceRef] = []
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None:
            raise ContractError(f"{event.event_id}: Event Understanding evidence is missing")
        if span.article_id not in event.article_ids:
            raise ContractError(f"{event.event_id}: Event Understanding evidence is outside event")
        field = (
            UnderstandingEvidenceField.TITLE
            if span.field is EvidenceField.TITLE
            else UnderstandingEvidenceField.BODY
        )
        refs.append(
            UnderstandingEvidenceRef.from_source(
                source,
                field=field,
                start=span.start,
                end=span.end,
            )
        )
    return tuple(refs)


def canonical_event_from_resolved_understanding(
    event: CandidateEvent,
    *,
    decision: CompatibilityEventUnderstandingDecision,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    source,
):
    """Promote one compatibility result through the provider-agnostic semantic contract.

    This adapter is temporary while a qualified EventUnderstandingPort is unavailable. It preserves
    the compatibility owner's semantic result but forbids the historical CandidateEvent ->
    CanonicalEvent direct lift.
    """

    if decision.status is not UnderstandingStatus.RESOLVED:
        raise ContractError("unresolved Event Understanding cannot become CanonicalEvent")
    if decision.article_role is not ArticleEventRole.PRIMARY or not decision.publishable_event:
        raise ContractError("only resolved publishable PRIMARY events cross the canonical boundary")
    if len(event.fact_ids) != 1:
        raise ContractError("compatibility Event Understanding requires one evidence-bound fact")
    fact = facts.get(event.fact_ids[0])
    if fact is None:
        raise ContractError(f"{event.event_id}: Event Understanding fact is missing")
    if len(fact.evidence_ids) != 1:
        raise ContractError(
            f"{event.event_id}: canonical primary requires exactly one source proposition"
        )

    draft = CanonicalEventDraft(
        draft_id=f"compat-understanding:{event.event_id}",
        topic=event.topic_id,
        actor=fact.subject,
        action=fact.action,
        object=fact.object,
        event_type="news_event",
        source_ids=(source.source_id,),
        evidence_refs=_understanding_evidence_refs(
            event=event,
            fact=fact,
            evidence=evidence,
            source=source,
        ),
        article_role=decision.article_role,
        topic_relation=decision.topic_relation,
        understanding_status=UnderstandingStatus.RESOLVED,
        event_time=_event_time(fact.event_date),
        participants=fact.participants,
        temporal_state=fact.temporal_state,
        certainty=fact.certainty,
        polarity=fact.polarity,
        location=fact.location,
        cause=fact.cause,
    )
    return canonical_event_from_draft(
        draft,
        event_id=event.event_id,
        publication_time=source.publication_time,
    )


class ProductionEventUnderstandingLifecycleOwner:
    """One reusable Event Understanding owner for publication and identity source expansion."""

    def __init__(self, registry: ProductionV2Registry, authoritative) -> None:
        self.registry = registry
        self.authoritative = authoritative
        self.decisions_by_event: dict[str, CompatibilityEventUnderstandingDecision] = {}
        self._morphology = _optional_morphology()
        self._extractor = None

    def bind_extractor(self, extractor) -> None:
        # Production constructs one resilient extractor for the run. Remember that exact helper so
        # bounded identity bridge sources traverse the same evidence-preparation path.
        self._extractor = extractor

    def _understand(
        self,
        *,
        article,
        result: SemanticArticleResult,
        persist: bool,
        cache_decisions: bool,
        enrich: bool,
    ) -> tuple[SemanticArticleResult, tuple[CanonicalEvent, ...]]:
        source = source_document_from_article(article)
        if persist:
            existing_source = self.registry.sources_by_article.get(article.article_id)
            if existing_source is not None and existing_source != source:
                raise ContractError(f"{article.article_id}: conflicting SourceDocument")
            self.registry.sources_by_article[article.article_id] = source

        if not result.events:
            return result, ()

        facts = {fact.fact_id: fact for fact in result.facts}
        evidence = {span.evidence_id: span for span in result.evidence}
        decisions = assess_compatibility_article_understanding(
            article=article,
            events=result.events,
            facts=facts,
            evidence=evidence,
            morphology=self._morphology,
            now=article.provenance.fetched_at,
        )

        retained: list[CandidateEvent] = []
        canonicals: list[CanonicalEvent] = []
        for event in result.events:
            decision = decisions[event.event_id]
            if cache_decisions:
                previous = self.decisions_by_event.get(event.event_id)
                if previous is not None and previous != decision:
                    raise ContractError(f"{event.event_id}: conflicting Event Understanding decision")
                self.decisions_by_event[event.event_id] = decision

            if decision.status is UnderstandingStatus.UNRESOLVED:
                if persist:
                    # Keep unresolved evidence available only for the bounded source-resolution lane.
                    # It has no CanonicalEvent and cannot reach authority/identity/generation.
                    retained.append(event)
                continue

            if decision.article_role is not ArticleEventRole.PRIMARY or not decision.publishable_event:
                continue

            canonical = canonical_event_from_resolved_understanding(
                event,
                decision=decision,
                facts=facts,
                evidence=evidence,
                source=source,
            )
            canonicals.append(canonical)

            if persist:
                existing_event = self.registry.events_by_id.get(event.event_id)
                if existing_event is not None and existing_event != canonical:
                    raise ContractError(f"{event.event_id}: conflicting CanonicalEvent")
                self.registry.events_by_id[event.event_id] = canonical

                if enrich:
                    authoritative = self.authoritative
                    official_facts = authoritative.enrich(canonical, source)
                    self.registry.bind_authoritative_facts(event.event_id, official_facts)
                retained.append(event)

        projected = SemanticArticleResult(
            article_id=result.article_id,
            extractor_id=result.extractor_id,
            evidence=result.evidence,
            facts=result.facts,
            events=tuple(retained),
        )
        return projected, tuple(canonicals)

    def process_publication_result(
        self,
        *,
        article,
        result: SemanticArticleResult,
    ) -> SemanticArticleResult:
        projected, _ = self._understand(
            article=article,
            result=result,
            persist=True,
            cache_decisions=True,
            enrich=True,
        )
        return projected

    def identity_bridge_events(self, article, *, topic_id: str) -> tuple[CanonicalEvent, ...]:
        """Interpret an additional source for identity only.

        The bridge uses the same extractor and Event Understanding owner as publication, but its
        SourceDocument and CanonicalEvent objects are ephemeral: they are not added to the registry,
        never enriched, and therefore cannot leak into publication.
        """

        if self._extractor is None:
            return ()
        result = LegacySemanticPipeline().extract_article(
            article,
            topic_id=topic_id,
            extractor=self._extractor,
        )
        _, canonicals = self._understand(
            article=article,
            result=result,
            persist=False,
            cache_decisions=False,
            enrich=False,
        )
        return canonicals

    def project(self, event: CandidateEvent) -> CompatibilityEventUnderstandingDecision:
        decision = self.decisions_by_event.get(event.event_id)
        if decision is None:
            raise ContractError(f"{event.event_id}: Event Understanding projection is missing")
        return decision


def install_event_understanding_lifecycle(
    core_module: ModuleType,
    registry: ProductionV2Registry,
) -> ProductionEventUnderstandingLifecycleOwner:
    """Install one active Event Understanding owner after Source and before CanonicalEvent."""

    authoritative = getattr(core_module, "_INSIGHT_DESK_V2_AUTHORITATIVE_OWNER", None)
    if authoritative is None:
        raise ContractError("authoritative owner must be installed before Event Understanding lifecycle")

    owner = ProductionEventUnderstandingLifecycleOwner(registry, authoritative)

    class EventUnderstandingSemanticPipeline:
        def __init__(self, *args, **kwargs) -> None:
            # Deliberately bypass the historical canonicalizing compatibility wrapper. Deterministic
            # extraction is only evidence preparation for the Event Understanding owner below.
            self._inner = LegacySemanticPipeline(*args, **kwargs)

        def extract_article(self, article, *, topic_id: str, extractor):
            owner.bind_extractor(extractor)
            result = self._inner.extract_article(
                article,
                topic_id=topic_id,
                extractor=extractor,
            )
            return owner.process_publication_result(
                article=article,
                result=result,
            )

    def project_event_understanding(
        event,
        *,
        facts,
        evidence,
        morphology,
        now,
    ):
        # The legacy loop still asks for a per-event decision. This is a projection of the single
        # article-scope result, not a second semantic judgment.
        del facts, evidence, morphology, now
        return owner.project(event)

    core_module.SemanticPipeline = EventUnderstandingSemanticPipeline
    core_module.event_understanding_decision = project_event_understanding
    return owner
