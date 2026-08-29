from __future__ import annotations

"""Production compatibility orchestrator for the CanonicalEvent V2 migration.

This module changes ownership, not news meaning. The legacy production loop remains the
mechanical iterator while its semantic decision hooks are replaced by one-owner V2 boundaries.
The compatibility layer is intentionally removable after the loop itself is rewritten around the
V2 contracts.
"""

from dataclasses import dataclass, field, replace
from datetime import date
import hashlib
from types import ModuleType
from typing import Mapping

from insight_desk.authoritative_enrichment_v2 import AuthoritativeEnricher
from insight_desk.core import (
    AuthoritativeFact,
    CandidateEvent,
    CanonicalEvent,
    CanonicalPublicationBundle,
    ContractError,
    EventFact,
    EvidenceSpan,
    RenderedBriefing,
    RenderedEntry,
    SourceDocument,
    VerifiedPublication,
    VerificationVerdict,
)
from insight_desk.core.contracts import ContractBundle as LegacyContractBundle
from insight_desk.publication_identity_v2 import PublicationIdentityManifest
from insight_desk.semantic.identity import (
    SemanticIdentityJudgment,
    resolve_candidate_pair as legacy_resolve_candidate_pair,
)
from insight_desk.semantic.events import compare_candidate_identity as legacy_compare_candidate_identity
from insight_desk.semantic.material import (
    MaterialEventAssessment,
    MaterialEventReason,
    MaterialEventVerdict,
)
from insight_desk.semantic.pipeline import SemanticPipeline as LegacySemanticPipeline
from insight_desk.semantic.visible_identity import (
    _same_scheduled_bok_policy_decision,
    visible_event_redundant as legacy_visible_event_redundant,
)


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts)
    return f"{prefix}-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _canonical_event_time(value: str | None) -> str | None:
    """Carry only already-resolved ISO dates into CanonicalEvent; never guess a date."""

    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def source_document_from_article(article) -> SourceDocument:
    """Bind one acquired article to exact body bytes before semantic processing continues."""

    return SourceDocument(
        source_id=f"source-document:{article.article_id}",
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


def canonical_event_from_candidate(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    source: SourceDocument,
) -> CanonicalEvent:
    """Lift the current evidence-bound one-fact candidate into the V2 event contract.

    Phase 4 does not invent a new model role. Existing evidence extraction remains an auxiliary
    input, while this builder becomes the only runtime component allowed to create CanonicalEvent.
    A richer semantic event type can replace ``news_event`` later without changing downstream
    contracts.
    """

    if len(event.fact_ids) != 1:
        raise ContractError("V2 production bridge requires one pre-identity EventFact per candidate")
    fact = facts.get(event.fact_ids[0])
    if fact is None:
        raise ContractError(f"{event.event_id}: missing fact for canonical event")
    return CanonicalEvent(
        event_id=event.event_id,
        topic=event.topic_id,
        actor=fact.subject,
        action=fact.action,
        object=fact.object,
        event_type="news_event",
        source_ids=(source.source_id,),
        event_time=_canonical_event_time(fact.event_date),
        publication_time=source.publication_time,
        participants=fact.participants,
        fact_ids=(fact.fact_id,),
        evidence_ids=fact.evidence_ids,
        temporal_state=fact.temporal_state,
        certainty=fact.certainty,
        polarity=fact.polarity,
        location=fact.location,
        cause=fact.cause,
    )


def _unique(values):
    return tuple(dict.fromkeys(values))


@dataclass(slots=True)
class ProductionV2Registry:
    sources_by_article: dict[str, SourceDocument] = field(default_factory=dict)
    events_by_id: dict[str, CanonicalEvent] = field(default_factory=dict)
    parent_events_by_id: dict[str, CanonicalEvent] = field(default_factory=dict)
    authoritative_facts_by_id: dict[str, AuthoritativeFact] = field(default_factory=dict)
    publications_by_event: dict[str, VerifiedPublication] = field(default_factory=dict)
    current_identity_pair: tuple[str, str] | None = None
    current_identity_relation: str | None = None
    v2_bundle_validated: bool = False

    def register_article_result(self, article, semantic_result) -> None:
        source = source_document_from_article(article)
        self.sources_by_article[article.article_id] = source
        facts = {fact.fact_id: fact for fact in semantic_result.facts}
        for event in semantic_result.events:
            self.events_by_id[event.event_id] = canonical_event_from_candidate(
                event,
                facts=facts,
                source=source,
            )

    def canonical_event(self, event_id: str) -> CanonicalEvent:
        try:
            return self.events_by_id[event_id]
        except KeyError as exc:
            raise ContractError(f"production event missing CanonicalEvent: {event_id}") from exc

    def source_for_event(self, event_id: str) -> SourceDocument:
        event = self.canonical_event(event_id)
        if len(event.source_ids) != 1:
            raise ContractError(f"pre-publication event must have one primary source: {event_id}")
        source_id = event.source_ids[0]
        for source in self.sources_by_article.values():
            if source.source_id == source_id:
                return source
        raise ContractError(f"canonical event missing SourceDocument: {event_id}:{source_id}")

    def bind_authoritative_facts(
        self,
        event_id: str,
        facts: tuple[AuthoritativeFact, ...],
    ) -> None:
        if not facts:
            return
        event = self.canonical_event(event_id)
        for fact in facts:
            existing = self.authoritative_facts_by_id.get(fact.fact_id)
            if existing is not None and existing != fact:
                raise ContractError(f"conflicting authoritative fact id: {fact.fact_id}")
            self.authoritative_facts_by_id[fact.fact_id] = fact
        fact_ids = _unique(
            event.authoritative_fact_ids + tuple(fact.fact_id for fact in facts)
        )
        self.events_by_id[event_id] = replace(
            event,
            authoritative_fact_ids=fact_ids,
        )

    def bind_policy_parent(self, left_id: str, right_id: str) -> None:
        left = self.canonical_event(left_id)
        right = self.canonical_event(right_id)
        event_time = left.event_time if left.event_time == right.event_time else None
        if event_time:
            parent_id = f"canonical-parent:bok_mpc:{event_time}"
        else:
            parent_id = _stable_id(
                "canonical-parent:bok_mpc",
                *sorted(left.source_ids + right.source_ids),
            )
        source_ids = _unique(left.source_ids + right.source_ids)
        authoritative_ids = _unique(
            left.authoritative_fact_ids + right.authoritative_fact_ids
        )
        parent = self.parent_events_by_id.get(parent_id)
        if parent is None:
            parent = CanonicalEvent(
                event_id=parent_id,
                topic=left.topic,
                actor=left.actor,
                action=left.action,
                object=left.object,
                event_type="policy_meeting_parent",
                source_ids=source_ids,
                event_time=event_time,
                publication_time=None,
                participants=_unique(left.participants + right.participants),
                authoritative_fact_ids=authoritative_ids,
            )
        else:
            parent = replace(
                parent,
                source_ids=_unique(parent.source_ids + source_ids),
                participants=_unique(parent.participants + left.participants + right.participants),
                authoritative_fact_ids=_unique(
                    parent.authoritative_fact_ids + authoritative_ids
                ),
            )
        self.parent_events_by_id[parent_id] = parent
        self.events_by_id[left_id] = replace(left, parent_event_id=parent_id)
        self.events_by_id[right_id] = replace(right, parent_event_id=parent_id)


class CanonicalIdentityEngine:
    """Single runtime owner for same/different/parent-child event identity."""

    def __init__(self, registry: ProductionV2Registry) -> None:
        self.registry = registry

    def visible_redundant(self, **_kwargs) -> bool:
        # Generated headline/summary surfaces are not an event-identity authority in V2.
        return False

    def precheck(
        self,
        left: CandidateEvent,
        right: CandidateEvent,
        facts: Mapping[str, EventFact],
        *,
        semantic_same_event: bool | None = None,
    ):
        self.registry.current_identity_pair = (left.event_id, right.event_id)
        self.registry.current_identity_relation = None
        return legacy_compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=semantic_same_event,
        )

    def judge(
        self,
        left_text: str,
        right_text: str,
        *,
        primary,
        secondary,
    ) -> SemanticIdentityJudgment:
        pair = self.registry.current_identity_pair
        if pair is not None:
            left_event = self.registry.canonical_event(pair[0])
            right_event = self.registry.canonical_event(pair[1])
            left_source = self.registry.source_for_event(pair[0]).body
            right_source = self.registry.source_for_event(pair[1]).body
            if (
                left_event.topic == "economy"
                and right_event.topic == "economy"
                and _same_scheduled_bok_policy_decision(left_source, right_source)
            ):
                self.registry.bind_policy_parent(*pair)
                self.registry.current_identity_relation = "parent_child"
                return SemanticIdentityJudgment(
                    True,
                    "canonical_parent_child:bok_policy_meeting",
                    0,
                    0,
                )

            # Retain only already-proven source fingerprints as an auxiliary inside the
            # canonical identity owner. Visible generated text is deliberately blanked.
            if legacy_visible_event_redundant(
                topic_id=left_event.topic,
                prior_headline="",
                prior_summary="",
                candidate_headline="",
                candidate_summary="",
                prior_source_text=right_source,
                candidate_source_text=left_source,
            ):
                self.registry.current_identity_relation = "same_event_source_fingerprint"
                return SemanticIdentityJudgment(
                    True,
                    "canonical_same_event:source_fingerprint",
                    0,
                    0,
                )

        # Claim-verification providers are not an event-identity authority. The compatibility
        # signature keeps primary/secondary until the legacy loop is removed, but they are never
        # consulted here. Unresolved identity remains DEFER rather than becoming different-event.
        del left_text, right_text, primary, secondary
        self.registry.current_identity_relation = "defer"
        return SemanticIdentityJudgment(
            None,
            "canonical_identity_unresolved_requires_identity_resolution",
            0,
            0,
        )

    def resolve(
        self,
        left: CandidateEvent,
        right: CandidateEvent,
        facts: Mapping[str, EventFact],
        *,
        semantic_same_event: bool | None = None,
    ):
        try:
            return legacy_resolve_candidate_pair(
                left,
                right,
                facts,
                semantic_same_event=semantic_same_event,
            )
        finally:
            self.registry.current_identity_pair = None


def _evidence_integrity_assessment(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    **_kwargs,
) -> MaterialEventAssessment:
    """Mechanical provenance integrity only; no second semantic material-event classifier."""

    for fact_id in event.fact_ids:
        fact = facts.get(fact_id)
        if fact is None:
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_MISSING,),
            )
        cited: list[str] = []
        for evidence_id in fact.evidence_ids:
            span = evidence.get(evidence_id)
            if span is None:
                return MaterialEventAssessment(
                    event.event_id,
                    MaterialEventVerdict.DEFER,
                    (MaterialEventReason.EVIDENCE_MISSING,),
                )
            if span.article_id not in event.article_ids:
                return MaterialEventAssessment(
                    event.event_id,
                    MaterialEventVerdict.DEFER,
                    (MaterialEventReason.EVIDENCE_OUTSIDE_EVENT,),
                )
            cited.append(span.text)
        cited_text = "\n".join(cited)
        literal_fields = (fact.subject, fact.action) + (
            (fact.object,) if fact.object is not None else ()
        )
        if any(value not in cited_text for value in literal_fields):
            return MaterialEventAssessment(
                event.event_id,
                MaterialEventVerdict.DEFER,
                (MaterialEventReason.FACT_FIELD_NOT_LITERAL,),
            )
    return MaterialEventAssessment(
        event.event_id,
        MaterialEventVerdict.MATERIAL,
        (MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE,),
    )


def _no_story_readmission(*_args, **_kwargs) -> None:
    """Generation is not allowed to reclassify an already canonicalized event."""

    return None


def _build_verified_publication(
    registry: ProductionV2Registry,
    candidate,
    *,
    verified_at,
) -> VerifiedPublication:
    if not candidate.publishable:
        raise ContractError(f"non-publishable Phase7 candidate reached publication: {candidate.event_id}")
    event = registry.canonical_event(candidate.event_id)
    source = registry.source_for_event(candidate.event_id)
    claims = tuple(item.claim for item in candidate.verification.claims)
    if not claims or any(claim.verdict is not VerificationVerdict.SUPPORTED for claim in claims):
        raise ContractError(f"publication requires supported claims: {candidate.event_id}")
    claim_ids = _unique(tuple(claim.claim_id for claim in claims))
    check_ids = _unique(
        tuple(check.check_id for claim in claims for check in claim.checks)
    )
    draft = candidate.final_generation.draft
    publication_id = _stable_id(
        "publication",
        event.event_id,
        draft.headline,
        draft.summary,
        *claim_ids,
        *check_ids,
    )
    return VerifiedPublication(
        publication_id=publication_id,
        event_id=event.event_id,
        topic=event.topic,
        headline=draft.headline,
        summary=draft.summary,
        source_ids=event.source_ids,
        primary_source_url=source.url,
        claim_ids=claim_ids,
        verification_check_ids=check_ids,
        verified_at=verified_at,
        render_mode=candidate.final_generation.render_mode,
        event_time=event.event_time,
        publication_time=event.publication_time,
        parent_event_id=event.parent_event_id,
        authoritative_fact_ids=event.authoritative_fact_ids,
    )


def install_production_orchestration(core_module: ModuleType) -> ProductionV2Registry:
    """Install V2 owners onto the legacy mechanical loop exactly once."""

    existing = getattr(core_module, "_INSIGHT_DESK_V2_REGISTRY", None)
    if isinstance(existing, ProductionV2Registry):
        return existing

    registry = ProductionV2Registry()
    identity = CanonicalIdentityEngine(registry)
    authoritative = AuthoritativeEnricher.from_environment()
    publication_manifest: PublicationIdentityManifest | None = None

    legacy_topic_relevant = core_module.topic_relevant
    legacy_relevance_decision = core_module.relevance_decision
    legacy_build_view = core_module.build_briefing_view_model
    legacy_write_json = core_module._write_json

    class CanonicalSemanticPipeline:
        def __init__(self, *args, **kwargs) -> None:
            self._inner = LegacySemanticPipeline(*args, **kwargs)

        def extract_article(self, article, *, topic_id: str, extractor):
            result = self._inner.extract_article(
                article,
                topic_id=topic_id,
                extractor=extractor,
            )
            registry.register_article_result(article, result)
            for event in result.events:
                canonical = registry.canonical_event(event.event_id)
                source = registry.source_for_event(event.event_id)
                official_facts = authoritative.enrich(canonical, source)
                registry.bind_authoritative_facts(event.event_id, official_facts)
            return result

    class V2BoundContractBundle:
        def __init__(self, **kwargs) -> None:
            self._legacy = LegacyContractBundle(**kwargs)
            self._briefing = kwargs.get("briefing")

        def validate(self) -> None:
            self._legacy.validate()
            publications = tuple(registry.publications_by_event.values())
            if self._briefing is not None:
                expected = tuple(entry.event_id for entry in self._briefing.entries)
                actual = tuple(publication.event_id for publication in publications)
                if expected != actual:
                    raise ContractError(
                        "VerifiedPublication order/identity differs from rendered briefing"
                    )
            selected_event_ids = {publication.event_id for publication in publications}
            selected_events = tuple(
                registry.canonical_event(event_id) for event_id in selected_event_ids
            )
            parent_ids = {
                event.parent_event_id
                for event in selected_events
                if event.parent_event_id is not None
            }
            parent_events = tuple(
                registry.parent_events_by_id[parent_id]
                for parent_id in parent_ids
                if parent_id in registry.parent_events_by_id
            )
            source_ids = {
                source_id
                for publication in publications
                for source_id in publication.source_ids
            }
            for event in parent_events + selected_events:
                source_ids.update(event.source_ids)
            selected_sources = tuple(
                source
                for source in registry.sources_by_article.values()
                if source.source_id in source_ids
            )
            authoritative_ids = {
                fact_id
                for event in parent_events + selected_events
                for fact_id in event.authoritative_fact_ids
            }
            selected_authoritative = tuple(
                fact
                for fact_id, fact in registry.authoritative_facts_by_id.items()
                if fact_id in authoritative_ids
            )
            bundle = CanonicalPublicationBundle(
                sources=selected_sources,
                authoritative_facts=selected_authoritative,
                events=parent_events + selected_events,
                publications=publications,
            )
            bundle.validate()
            registry.v2_bundle_validated = True

    def source_relevance_decision(*, title: str, body: str, topic):
        # The migration installs one typed relevance owner. The underlying configured-literal
        # policy remains unchanged here; later phases may improve resolution without changing the
        # RelevanceDecision contract consumed by production.
        return legacy_relevance_decision(title=title, body=body, topic=topic)

    def source_relevant(*, title: str, body: str, topic) -> bool:
        # Compatibility bool projection only. Daily production consumes the typed decision above.
        return source_relevance_decision(title=title, body=body, topic=topic).is_relevant

    def event_relevant(*, event, facts, evidence, topic) -> bool:
        del facts, evidence
        canonical = registry.canonical_event(event.event_id)
        return canonical.topic == topic.topic_id

    def build_rendered_briefing_v2(*, briefing_id: str, generated_at, candidates):
        publications = tuple(
            _build_verified_publication(
                registry,
                candidate,
                verified_at=generated_at,
            )
            for candidate in candidates
        )
        registry.publications_by_event = {
            publication.event_id: publication for publication in publications
        }
        return RenderedBriefing(
            briefing_id=briefing_id,
            generated_at=generated_at,
            entries=tuple(
                RenderedEntry(
                    event_id=publication.event_id,
                    headline=publication.headline,
                    summary=publication.summary,
                    claim_ids=publication.claim_ids,
                    render_mode=publication.render_mode,
                )
                for publication in publications
            ),
        )

    def build_view_v2(briefing, *, topic_by_event=None, source_by_event=None):
        nonlocal publication_manifest
        del topic_by_event, source_by_event
        topics = {
            event_id: publication.topic
            for event_id, publication in registry.publications_by_event.items()
        }
        sources = {
            event_id: publication.primary_source_url
            for event_id, publication in registry.publications_by_event.items()
        }
        publication_manifest = PublicationIdentityManifest.from_verified(
            briefing.briefing_id,
            tuple(registry.publications_by_event.values()),
        )
        return legacy_build_view(
            briefing,
            topic_by_event=topics,
            source_by_event=sources,
            publication_by_event=registry.publications_by_event,
        )

    def write_json_v2(path, payload) -> None:
        if not isinstance(payload, dict):
            legacy_write_json(path, payload)
            return

        if payload.get("publish") is True and "briefing_id" in payload and "published_entries" in payload:
            if publication_manifest is None:
                raise ContractError("published V2 state missing publication identity manifest")
            if str(payload.get("briefing_id")) != publication_manifest.briefing_id:
                raise ContractError("run state briefing identity differs from PWA publication identity")
            payload = {
                **payload,
                "publication_contract_version": publication_manifest.version,
                "publication_digest": publication_manifest.sha256,
                "publication_ids": list(publication_manifest.publication_ids),
            }

        if "rendered_sources" in payload and "provider_roles" in payload:
            if payload.get("publish") is True and publication_manifest is None:
                raise ContractError("published V2 audit missing publication identity manifest")
            payload = {
                **payload,
                "publication_contract_version": 2,
                "canonical_contract": {
                    "source_documents": len(registry.sources_by_article),
                    "canonical_events": len(registry.events_by_id),
                    "parent_events": len(registry.parent_events_by_id),
                    "authoritative_facts": len(registry.authoritative_facts_by_id),
                    "verified_publications": len(registry.publications_by_event),
                    "validated": registry.v2_bundle_validated,
                },
                "publication_identity": (
                    {
                        "briefing_id": publication_manifest.briefing_id,
                        "sha256": publication_manifest.sha256,
                        "publication_ids": list(publication_manifest.publication_ids),
                    }
                    if publication_manifest is not None
                    else None
                ),
                "authoritative_enrichment": authoritative.audit_stats,
                "runtime_authority": {
                    "relevance": "relevance_engine",
                    "event_understanding": "canonical_event_builder",
                    "authoritative_enrichment": "authoritative_enricher",
                    "event_identity": "canonical_identity_engine",
                    "generation": "publication_generator",
                    "verification": "claim_verification_engine",
                    "publication": "publication_contract",
                    "rendering": "pwa_renderer",
                    "story_admission_semantic_gate": False,
                    "visible_identity_semantic_gate": False,
                },
            }
        legacy_write_json(path, payload)

    # Install one owner per semantic responsibility onto the old loop. The old implementations
    # stay importable for historical replay, but are no longer runtime authorities here.
    core_module.SemanticPipeline = CanonicalSemanticPipeline
    core_module.relevance_decision = source_relevance_decision
    core_module.topic_relevant = source_relevant
    core_module.event_topic_relevant = event_relevant
    core_module.assess_material_event = _evidence_integrity_assessment
    core_module._visible_topic_headline_bound = lambda _topic, _headline: True
    core_module.visible_story_issues = lambda **_kwargs: ()
    core_module.visible_event_redundant = identity.visible_redundant
    core_module.compare_candidate_identity = identity.precheck
    core_module.judge_same_event_mutual_entailment = identity.judge
    core_module.resolve_candidate_pair = identity.resolve
    core_module.build_rendered_briefing = build_rendered_briefing_v2
    core_module.build_briefing_view_model = build_view_v2
    core_module.ContractBundle = V2BoundContractBundle
    core_module._write_json = write_json_v2

    # The entrypoint immediately scopes these two assignments to the actual production Phase7 call.
    # They are set here first so an accidental direct use of the core module still cannot silently
    # reactivate semantic re-admission after a CanonicalEvent already exists.
    import insight_desk.generation as generation_module
    import insight_desk.generation_pipeline as generation_pipeline_module

    generation_module.validate_story_admission = _no_story_readmission
    generation_pipeline_module.validate_story_admission = _no_story_readmission

    core_module._INSIGHT_DESK_V2_REGISTRY = registry
    core_module._INSIGHT_DESK_V2_IDENTITY_OWNER = identity
    core_module._INSIGHT_DESK_V2_AUTHORITATIVE_OWNER = authoritative
    return registry