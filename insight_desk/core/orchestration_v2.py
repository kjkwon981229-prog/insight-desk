from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PipelineResponsibility(StrEnum):
    DISCOVERY = "discovery"
    SOURCE = "source"
    RELEVANCE = "relevance"
    EVENT_UNDERSTANDING = "event_understanding"
    AUTHORITATIVE_ENRICHMENT = "authoritative_enrichment"
    EVENT_IDENTITY = "event_identity"
    GENERATION = "generation"
    VERIFICATION = "verification"
    PUBLICATION_CONTRACT = "publication_contract"
    RENDERING = "rendering"
    PUSH = "push"
    EXECUTION = "execution"


@dataclass(frozen=True, slots=True)
class OwnerBoundary:
    responsibility: PipelineResponsibility
    owner_id: str
    input_contract: str
    output_contract: str
    allowed_decisions: tuple[str, ...]
    forbidden_decisions: tuple[str, ...]
    semantic_authority: bool = False
    mechanical_only: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("owner_id", self.owner_id),
            ("input_contract", self.input_contract),
            ("output_contract", self.output_contract),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not self.allowed_decisions:
            raise ValueError("allowed_decisions must not be empty")
        if any(not item.strip() for item in self.allowed_decisions):
            raise ValueError("allowed_decisions must contain non-empty values")
        if any(not item.strip() for item in self.forbidden_decisions):
            raise ValueError("forbidden_decisions must contain non-empty values")
        if len(self.allowed_decisions) != len(set(self.allowed_decisions)):
            raise ValueError("allowed_decisions must be unique")
        if len(self.forbidden_decisions) != len(set(self.forbidden_decisions)):
            raise ValueError("forbidden_decisions must be unique")
        overlap = set(self.allowed_decisions) & set(self.forbidden_decisions)
        if overlap:
            raise ValueError(f"allowed and forbidden decisions overlap: {sorted(overlap)}")
        if self.mechanical_only and self.semantic_authority:
            raise ValueError("mechanical-only owner cannot have semantic authority")


OWNER_BOUNDARIES: tuple[OwnerBoundary, ...] = (
    OwnerBoundary(
        responsibility=PipelineResponsibility.DISCOVERY,
        owner_id="news_discovery",
        input_contract="TopicQuery",
        output_contract="ArticleCandidate",
        allowed_decisions=("discover_candidates", "record_discovery_provenance"),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "verify_claims"),
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.SOURCE,
        owner_id="source_acquisition",
        input_contract="ArticleCandidate",
        output_contract="SourceDocument",
        allowed_decisions=("fetch_source", "extract_article_body", "record_source_provenance"),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "verify_claims"),
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.RELEVANCE,
        owner_id="relevance_engine",
        input_contract="SourceDocument",
        output_contract="RelevanceDecision",
        allowed_decisions=("judge_user_relevance",),
        forbidden_decisions=("understand_event", "resolve_event_identity", "generate_copy", "verify_claims"),
        semantic_authority=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.EVENT_UNDERSTANDING,
        owner_id="canonical_event_builder",
        input_contract="RelevantSourceSet",
        output_contract="CanonicalEventDraft",
        allowed_decisions=("extract_event_meaning", "structure_event_facts", "identify_attribution"),
        forbidden_decisions=("select_publication_card", "resolve_event_identity", "generate_copy", "verify_claims"),
        semantic_authority=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.AUTHORITATIVE_ENRICHMENT,
        owner_id="authoritative_enricher",
        input_contract="CanonicalEventDraft",
        output_contract="EnrichedEventFacts",
        allowed_decisions=("query_authoritative_source", "attach_authoritative_fact"),
        forbidden_decisions=("judge_relevance", "resolve_event_identity", "generate_copy", "verify_claims"),
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.EVENT_IDENTITY,
        owner_id="canonical_identity_engine",
        input_contract="CanonicalEventDraftSet",
        output_contract="CanonicalEvent",
        allowed_decisions=("resolve_same_event", "resolve_distinct_event", "resolve_parent_child"),
        forbidden_decisions=("judge_relevance", "judge_story_quality", "generate_copy", "verify_claims"),
        semantic_authority=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.GENERATION,
        owner_id="publication_generator",
        input_contract="CanonicalEvent",
        output_contract="PublicationDraft",
        allowed_decisions=("express_headline", "express_summary"),
        forbidden_decisions=("judge_relevance", "resolve_event_identity", "invent_authoritative_fact", "verify_claims"),
        semantic_authority=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.VERIFICATION,
        owner_id="claim_verification_engine",
        input_contract="PublicationDraft+CanonicalEvent",
        output_contract="VerifiedClaims",
        allowed_decisions=("verify_claim_support", "mark_verification_indeterminate"),
        forbidden_decisions=("judge_relevance", "resolve_event_identity", "deduplicate_events", "generate_copy"),
        semantic_authority=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.PUBLICATION_CONTRACT,
        owner_id="publication_contract",
        input_contract="CanonicalEvent+VerifiedClaims",
        output_contract="VerifiedPublication",
        allowed_decisions=(
            "validate_required_fields",
            "validate_url",
            "validate_timestamp",
            "validate_ids",
            "validate_provenance_links",
            "validate_verification_presence",
        ),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "judge_story_quality"),
        mechanical_only=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.RENDERING,
        owner_id="pwa_renderer",
        input_contract="VerifiedPublicationSet",
        output_contract="PwaArtifact",
        allowed_decisions=("render_publication", "apply_display_layout"),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "verify_claims"),
        mechanical_only=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.PUSH,
        owner_id="push_dispatcher",
        input_contract="PublishedBriefingState",
        output_contract="PushDeliveryState",
        allowed_decisions=("deliver_publication_state", "deduplicate_delivery"),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "verify_claims"),
        mechanical_only=True,
    ),
    OwnerBoundary(
        responsibility=PipelineResponsibility.EXECUTION,
        owner_id="github_actions_orchestrator",
        input_contract="ProductionTrigger",
        output_contract="PipelineExecutionState",
        allowed_decisions=("invoke_stage", "pass_stage_output", "enforce_stage_order"),
        forbidden_decisions=("judge_relevance", "understand_event", "resolve_event_identity", "judge_story_quality", "verify_claims"),
        mechanical_only=True,
    ),
)


def owner_for(responsibility: PipelineResponsibility) -> OwnerBoundary:
    matches = tuple(item for item in OWNER_BOUNDARIES if item.responsibility is responsibility)
    if len(matches) != 1:
        raise RuntimeError(f"single-owner contract violated for {responsibility.value}: {len(matches)} owners")
    return matches[0]


def validate_owner_boundaries() -> None:
    expected = set(PipelineResponsibility)
    actual = {item.responsibility for item in OWNER_BOUNDARIES}
    if actual != expected:
        missing = sorted(item.value for item in expected - actual)
        extra = sorted(item.value for item in actual - expected)
        raise RuntimeError(f"owner registry mismatch: missing={missing}, extra={extra}")
    if len(OWNER_BOUNDARIES) != len(actual):
        raise RuntimeError("one responsibility is assigned to more than one owner")

    owner_ids = tuple(item.owner_id for item in OWNER_BOUNDARIES)
    if len(owner_ids) != len(set(owner_ids)):
        raise RuntimeError("one owner_id is reused across responsibilities")

    publication = owner_for(PipelineResponsibility.PUBLICATION_CONTRACT)
    if not publication.mechanical_only:
        raise RuntimeError("publication contract must remain mechanical-only")
    if publication.semantic_authority:
        raise RuntimeError("publication contract must not acquire semantic authority")

    for responsibility in (
        PipelineResponsibility.RENDERING,
        PipelineResponsibility.PUSH,
        PipelineResponsibility.EXECUTION,
    ):
        boundary = owner_for(responsibility)
        if not boundary.mechanical_only or boundary.semantic_authority:
            raise RuntimeError(f"{responsibility.value} must remain a mechanical boundary")
