from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from insight_desk.acquisition import (
    AcquisitionError,
    AcquisitionPipeline,
    ArticleCandidate,
    DiscoveryError,
    PlaywrightHtmlRenderer,
    TrafilaturaExtractor,
    UrlLibHtmlFetcher,
    default_news_discovery,
)
from insight_desk.core import (
    CandidateEvent,
    ContractBundle,
    EventFact,
    EvidenceSpan,
    RelevanceDecision,
    RelevanceVerdict,
    SelectionVerdict,
    relevance_from_literal_match,
)
from insight_desk.core.event_understanding_v2 import ArticleEventRole, UnderstandingStatus
from insight_desk.core.identity import IdentityDisposition, identity_disposition
from insight_desk.feed_quality import visible_story_issues
from insight_desk.generation import GenerationRequest, Groq20BBriefingGenerator
from insight_desk.phase7 import Phase7EntryCandidate, produce_phase7_entry_candidate
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_event_understanding as event_understanding_decision,
)
from insight_desk.providers.cloudflare import CLOUDFLARE_MODEL, CloudflareClaimVerifier
from insight_desk.providers.groq import GROQ_20B, GroqFreeClient
from insight_desk.providers.local_nli import LOCAL_NLI_MODEL, LocalNliVerifier
from insight_desk.rendering import build_rendered_briefing
from insight_desk.semantic import (
    Phase6EventEngine,
    Phase6SelectionContext,
    SemanticPipeline,
    build_resilient_fact_extractor,
    compare_candidate_identity,
    judge_same_event_mutual_entailment,
    resolve_candidate_pair,
)
from insight_desk.semantic.material import MaterialEventVerdict
from insight_desk.story_admission import (
    StoryAdmissionInput,
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)
from insight_desk.ui import PwaRuntimeConfig, build_briefing_view_model, render_briefing_html


KST = timezone(timedelta(hours=9))
FRESHNESS_WINDOW = timedelta(hours=72)
FUTURE_CLOCK_TOLERANCE = timedelta(hours=6)
MAX_ACQUISITIONS_PER_TOPIC = 8
MAX_VERIFICATION_ATTEMPTS_PER_TOPIC = 6
MAX_IDENTITY_DEFER_RESOLUTION_ATTEMPTS_PER_TOPIC = 2
RELEVANCE_RESOLUTION_EXPANSION_LIMIT = 2
RELEVANCE_RESOLUTION_ACQUISITION_LIMIT = 2
EVENT_UNDERSTANDING_RESOLUTION_EXPANSION_LIMIT = 2
EVENT_UNDERSTANDING_RESOLUTION_ACQUISITION_LIMIT = 2


@dataclass(frozen=True, slots=True)
class TopicConfig:
    topic_id: str
    name: str
    priority: int
    candidate_budget: int
    selection_cap: int
    intent_anchors: tuple[str, ...]
    required_intent_terms: tuple[str, ...]
    news_queries: tuple[str, ...]
    event_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.topic_id or not self.name:
            raise ValueError("topic id/name must be non-empty")
        if self.candidate_budget < 1 or self.selection_cap < 1:
            raise ValueError("topic budgets must be positive")
        if not self.intent_anchors or not self.news_queries:
            raise ValueError("enabled production topic requires anchors and news queries")


@dataclass(frozen=True, slots=True)
class PublishedCandidate:
    topic: TopicConfig
    candidate: Phase7EntryCandidate
    source_group_key: str
    content_sha256: str
    identity_text: str
    source_identity_text: str
    source_url: str


def load_topics(path: Path) -> tuple[TopicConfig, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics: list[TopicConfig] = []
    for raw in payload.get("topics", []):
        if raw.get("enabled") is not True:
            continue
        topics.append(
            TopicConfig(
                topic_id=str(raw["id"]),
                name=str(raw["name"]),
                priority=int(raw.get("priority", 0)),
                candidate_budget=int(raw.get("candidate_budget", 8)),
                selection_cap=int(raw.get("selection_cap", 1)),
                intent_anchors=tuple(str(value) for value in raw.get("intent_anchors", []) if str(value).strip()),
                required_intent_terms=tuple(str(value) for value in raw.get("required_intent_terms", []) if str(value).strip()),
                news_queries=tuple(str(value) for value in raw.get("news_queries", []) if str(value).strip()),
                event_terms=tuple(str(value) for value in raw.get("event_terms", []) if str(value).strip()),
            )
        )
    return tuple(sorted(topics, key=lambda item: (-item.priority, item.topic_id)))


def _term_present(text: str, term: str) -> bool:
    """Acquisition-level configured literal matcher; not a story-admission policy."""
    term = term.strip()
    if not term:
        return False
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+&/-]*", term):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return term.casefold() in text.casefold()


def topic_relevant(*, title: str, body: str, topic: TopicConfig) -> bool:
    """Preserved article-acquisition preselection using configured source-query terms."""
    text = f"{title}\n{body}"
    if not any(_term_present(text, term) for term in topic.intent_anchors):
        return False
    if topic.required_intent_terms and not any(_term_present(text, term) for term in topic.required_intent_terms):
        return False
    return True


def relevance_decision(*, title: str, body: str, topic: TopicConfig) -> RelevanceDecision:
    """Compatibility lift from the preserved literal matcher into the typed owner contract."""

    return relevance_from_literal_match(
        topic_id=topic.topic_id,
        matched=topic_relevant(title=title, body=body, topic=topic),
    )


def _visible_topic_headline_bound(topic: TopicConfig, headline: str) -> bool:
    """Compatibility projection of the shared visible admission decision."""
    decision = evaluate_story_admission(
        topic=topic.name,
        headline=headline,
        summary=headline,
        source_text=headline,
        stage=StoryAdmissionStage.VISIBLE,
    )
    return StoryAdmissionReason.TOPIC_OWNERSHIP not in decision.reasons


def event_topic_relevant(
    *,
    event: CandidateEvent,
    facts: dict[str, EventFact],
    evidence: dict[str, EvidenceSpan],
    topic: TopicConfig,
) -> bool:
    """Compatibility bool projection of the one shared routing decision."""
    decision = evaluate_story_admission(
        StoryAdmissionInput(
            stage=StoryAdmissionStage.ROUTING,
            topic=topic.topic_id,
            event=event,
            facts=facts,
            evidence=evidence,
            intent_anchors=topic.intent_anchors,
            required_intent_terms=topic.required_intent_terms,
            event_terms=topic.event_terms,
        )
    )
    return decision.accepted


def _identity_defer_unresolved(*_args, **_kwargs):
    """Compatibility default; production V2 runtime injects the bounded source-resolution lane."""

    return None


resolve_deferred_identity = _identity_defer_unresolved


def _is_fresh(published_at: datetime | None, now: datetime) -> bool | None:
    """Preserved article-source acquisition freshness threshold."""
    if published_at is None:
        return None
    age = now.astimezone(timezone.utc) - published_at.astimezone(timezone.utc)
    return -FUTURE_CLOCK_TOLERANCE <= age <= FRESHNESS_WINDOW


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "unknown").lower()


def _source_group_key(candidate: ArticleCandidate) -> str:
    candidate_id = candidate.candidate_id[:-4] if candidate.candidate_id.endswith("-alt") else candidate.candidate_id
    return hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()


def _content_fingerprint(body: str) -> str:
    normalized = " ".join(body.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _candidate_budget_allows(
    *,
    candidate_url: str,
    relevance_resolution_candidate_urls: set[str],
    acquisition_attempts: int,
    max_acquisitions: int,
    relevance_resolution_acquisitions: int,
    event_understanding_resolution_candidate_urls: set[str] | None = None,
    event_understanding_resolution_acquisitions: int = 0,
) -> bool:
    understanding_urls = event_understanding_resolution_candidate_urls or set()
    if candidate_url in understanding_urls:
        return event_understanding_resolution_acquisitions < EVENT_UNDERSTANDING_RESOLUTION_ACQUISITION_LIMIT
    if candidate_url in relevance_resolution_candidate_urls:
        return relevance_resolution_acquisitions < RELEVANCE_RESOLUTION_ACQUISITION_LIMIT
    return acquisition_attempts < max_acquisitions


def _attempt(*, topic: str, query: str, domain: str, stage: str, status: str, reason: str | None = None) -> dict[str, object]:
    item: dict[str, object] = {"topic": topic, "query": query, "domain": domain, "stage": stage, "status": status}
    if reason is not None:
        item["reason"] = reason
    return item


def _counter(stats: dict[str, int], key: str, amount: int = 1) -> None:
    stats[key] = stats.get(key, 0) + amount


def _route_counter(stats: dict[str, dict[str, int]], route: str, key: str) -> None:
    bucket = stats.setdefault(route, {})
    bucket[key] = bucket.get(key, 0) + 1


def _record_generation_stats(
    candidate: Phase7EntryCandidate,
    generation_stats: dict[str, int],
    generation_route_stats: dict[str, dict[str, int]],
) -> None:
    results = [candidate.initial_generation]
    if candidate.final_generation is not candidate.initial_generation:
        results.append(candidate.final_generation)
    for result in results:
        for attempt in result.attempts:
            status_key = attempt.status.value
            generation_stats[status_key] = generation_stats.get(status_key, 0) + 1
            _route_counter(generation_route_stats, attempt.kind.value, status_key)
            if attempt.error_code:
                error_key = "error_" + attempt.error_code.split(":", 1)[0]
                _route_counter(generation_route_stats, attempt.kind.value, error_key)
        if result.render_mode.value == "extractive_fallback":
            generation_stats["extractive_fallback"] += 1
    if candidate.verification_recovery_reason is not None:
        generation_stats["verification_recovery_fallback"] += 1


def _record_verification_stats(candidate: Phase7EntryCandidate, verification_stats: dict[str, dict[str, int]]) -> None:
    for verified in candidate.verification.claims:
        for check in verified.claim.checks:
            model = check.model_id
            _route_counter(verification_stats, model, "checks")
            if check.entailed is True:
                _route_counter(verification_stats, model, "supported")
            elif check.entailed is False:
                _route_counter(verification_stats, model, "rejected")
            else:
                _route_counter(verification_stats, model, "unavailable")


def stage_site(output_dir: Path, html: str) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2("manifest.webmanifest", output_dir / "manifest.webmanifest")
    shutil.copy2("push-sw.js", output_dir / "push-sw.js")
    shutil.copytree("assets", output_dir / "assets")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_production(*, topics_path: Path, output_dir: Path, state_path: Path, audit_path: Path) -> dict[str, object]:
    topics = load_topics(topics_path)
    if not topics:
        raise RuntimeError("no enabled production topics")

    discovery = default_news_discovery()
    acquisition = AcquisitionPipeline(
        fetcher=UrlLibHtmlFetcher(timeout=15),
        primary_extractor=TrafilaturaExtractor(),
        fallback_renderer=PlaywrightHtmlRenderer(timeout_ms=20_000),
    )
    semantic = SemanticPipeline()
    extractor = build_resilient_fact_extractor()
    phase6 = Phase6EventEngine()
    generator = Groq20BBriefingGenerator(GroqFreeClient.from_env(GROQ_20B)) if GroqFreeClient.configured(model_id=GROQ_20B) else None
    primary_verifier = CloudflareClaimVerifier.from_env()
    local_verifier: LocalNliVerifier | None = None

    now = datetime.now(timezone.utc)
    seen_urls: set[str] = set()
    published_source_groups: set[str] = set()
    published_content_fingerprints: set[str] = set()
    published: list[PublishedCandidate] = []
    attempts: list[dict[str, object]] = []
    topic_stats: dict[str, dict[str, int]] = {}
    generation_stats: dict[str, int] = {
        "accepted": 0,
        "provider_error": 0,
        "output_contract_rejected": 0,
        "preservation_rejected": 0,
        "extractive_fallback": 0,
        "verification_recovery_fallback": 0,
        "extractive_fallback_unavailable": 0,
    }
    generation_route_stats: dict[str, dict[str, int]] = {}
    verification_stats: dict[str, dict[str, int]] = {}
    acquisition_stats: dict[str, dict[str, int]] = {"selected_methods": {}, "failures": {}}
    identity_stats: dict[str, int] = {
        "comparisons": 0,
        "deterministic_blocks": 0,
        "secondary_checks": 0,
        "primary_checks": 0,
        "same_event": 0,
        "different_event": 0,
        "unavailable": 0,
        "deferred": 0,
        "defer_resolution_attempts": 0,
        "defer_resolution_same_event": 0,
        "defer_resolution_held": 0,
    }

    articles: dict[str, object] = {}
    evidence: dict[str, object] = {}
    facts: dict[str, object] = {}
    events: dict[str, object] = {}
    claims: dict[str, object] = {}

    for topic in topics:
        stats = {
            "acquisition_attempts": 0,
            "acquired_articles": 0,
            "semantic_events": 0,
            "material_events": 0,
            "included_events": 0,
            "verification_attempts": 0,
            "identity_resolution_attempts": 0,
            "relevance_resolution_expansions": 0,
            "relevance_resolution_candidates": 0,
            "relevance_resolution_acquisitions": 0,
            "event_understanding_resolution_expansions": 0,
            "event_understanding_resolution_candidates": 0,
            "event_understanding_resolution_acquisitions": 0,
            "published_entries": 0,
        }
        topic_stats[topic.topic_id] = stats
        max_acquisitions = min(topic.candidate_budget, MAX_ACQUISITIONS_PER_TOPIC)
        relevance_resolution_candidate_urls: set[str] = set()
        event_understanding_resolution_candidate_urls: set[str] = set()

        for query in topic.news_queries:
            if stats["acquisition_attempts"] >= max_acquisitions or stats["published_entries"] >= topic.selection_cap:
                break
            try:
                queue = list(discovery.search(query, topic_id=topic.topic_id, limit=10))
            except DiscoveryError as exc:
                attempts.append(_attempt(topic=topic.topic_id, query=query, domain="discovery", stage="discovery", status="skip", reason=exc.failure_kind.value))
                continue

            for candidate in queue:
                candidate_url = str(getattr(candidate, "url", "") or "").strip()
                if stats["published_entries"] >= topic.selection_cap:
                    break
                if not _candidate_budget_allows(
                    candidate_url=candidate_url,
                    relevance_resolution_candidate_urls=relevance_resolution_candidate_urls,
                    event_understanding_resolution_candidate_urls=event_understanding_resolution_candidate_urls,
                    acquisition_attempts=stats["acquisition_attempts"],
                    max_acquisitions=max_acquisitions,
                    relevance_resolution_acquisitions=stats["relevance_resolution_acquisitions"],
                    event_understanding_resolution_acquisitions=stats["event_understanding_resolution_acquisitions"],
                ):
                    if candidate_url in event_understanding_resolution_candidate_urls:
                        attempts.append(_attempt(
                            topic=topic.topic_id,
                            query=query,
                            domain=_domain(candidate_url),
                            stage="event_understanding_resolution",
                            status="defer",
                            reason="event_understanding_defer:resolution_acquisition_budget_exhausted",
                        ))
                    elif candidate_url in relevance_resolution_candidate_urls:
                        attempts.append(_attempt(
                            topic=topic.topic_id,
                            query=query,
                            domain=_domain(candidate_url),
                            stage="event_topic_relevance_resolution",
                            status="defer",
                            reason="relevance_defer:resolution_acquisition_budget_exhausted",
                        ))
                    continue
                if candidate.url in seen_urls:
                    continue
                seen_urls.add(candidate.url)
                source_group_key = _source_group_key(candidate)
                if source_group_key in published_source_groups:
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=_domain(candidate.url), stage="source_identity", status="skip", reason="source_group_already_published"))
                    continue
                if candidate_url in event_understanding_resolution_candidate_urls:
                    stats["event_understanding_resolution_acquisitions"] += 1
                elif candidate_url in relevance_resolution_candidate_urls:
                    stats["relevance_resolution_acquisitions"] += 1
                else:
                    stats["acquisition_attempts"] += 1
                domain = _domain(candidate.url)

                try:
                    acquired = acquisition.acquire(candidate)
                except AcquisitionError as exc:
                    _counter(acquisition_stats["failures"], exc.failure_kind.value)
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="acquisition", status="skip", reason=exc.failure_kind.value))
                    continue

                _counter(acquisition_stats["selected_methods"], acquired.extraction_method)
                stats["acquired_articles"] += 1
                article = acquired.article
                content_sha256 = _content_fingerprint(article.body)
                if content_sha256 in published_content_fingerprints:
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="source_identity", status="skip", reason="content_fingerprint_already_published"))
                    continue
                fresh = _is_fresh(article.provenance.published_at, now)
                if fresh is not True:
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="freshness", status="skip", reason="published_at_missing" if fresh is None else "outside_72h_window"))
                    continue

                source_relevance = relevance_decision(title=article.title, body=article.body, topic=topic)
                if source_relevance.verdict is RelevanceVerdict.IRRELEVANT:
                    attempts.append(_attempt(
                        topic=topic.topic_id,
                        query=query,
                        domain=domain,
                        stage="topic_relevance",
                        status="skip",
                        reason=source_relevance.reasons[0].value,
                    ))
                    continue
                if source_relevance.verdict is RelevanceVerdict.DEFER:
                    attempts.append(_attempt(
                        topic=topic.topic_id,
                        query=query,
                        domain=domain,
                        stage="topic_relevance",
                        status="defer",
                        reason=source_relevance.reasons[0].value,
                    ))
                    continue

                semantic_result = semantic.extract_article(article, topic_id=topic.topic_id, extractor=extractor)
                if not semantic_result.events:
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="semantic", status="skip", reason="no_deterministic_fact"))
                    continue

                article_facts = {item.fact_id: item for item in semantic_result.facts}
                article_evidence = {item.evidence_id: item for item in semantic_result.evidence}
                stats["semantic_events"] += len(semantic_result.events)

                for event in semantic_result.events:
                    if stats["published_entries"] >= topic.selection_cap:
                        break
                    event_relevant = event_topic_relevant(event=event, facts=article_facts, evidence=article_evidence, topic=topic)
                    if not event_relevant:
                        attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="event_topic_relevance", status="skip", reason="configured_literal_missing_in_event_evidence"))
                        if (
                            stats["relevance_resolution_expansions"] < RELEVANCE_RESOLUTION_EXPANSION_LIMIT
                            and "expand_deferred_event_relevance" in globals()
                        ):
                            expansion = expand_deferred_event_relevance(
                                event=event,
                                facts=article_facts,
                                topic=topic,
                                discovery=discovery,
                            )
                            if expansion is not None and getattr(expansion, "attempted", False):
                                stats["relevance_resolution_expansions"] += 1
                                queued_urls = {
                                    str(getattr(queued_candidate, "url", "") or "").strip()
                                    for queued_candidate in queue
                                }
                                appended = 0
                                for expanded_candidate in getattr(expansion, "candidates", ()):
                                    expanded_url = str(getattr(expanded_candidate, "url", "") or "").strip()
                                    if not expanded_url or expanded_url in seen_urls or expanded_url in queued_urls:
                                        continue
                                    queue.append(expanded_candidate)
                                    queued_urls.add(expanded_url)
                                    relevance_resolution_candidate_urls.add(expanded_url)
                                    appended += 1
                                stats["relevance_resolution_candidates"] += appended
                                attempts.append(_attempt(
                                    topic=topic.topic_id,
                                    query=query,
                                    domain=domain,
                                    stage="event_topic_relevance_resolution",
                                    status="expanded" if appended else "defer",
                                    reason=str(getattr(expansion, "reason", "relevance_defer:resolution_unknown")),
                                ))
                        continue

                    understanding = event_understanding_decision(
                        event,
                        facts=article_facts,
                        evidence=article_evidence,
                        morphology=None,
                        now=now,
                    )
                    if understanding.status is UnderstandingStatus.UNRESOLVED:
                        attempts.append(_attempt(
                            topic=topic.topic_id,
                            query=query,
                            domain=domain,
                            stage="event_understanding",
                            status="defer",
                            reason=understanding.reasons[0] if understanding.reasons else "understanding_unresolved",
                        ))
                        if (
                            stats["event_understanding_resolution_expansions"] < EVENT_UNDERSTANDING_RESOLUTION_EXPANSION_LIMIT
                            and "expand_deferred_event_understanding" in globals()
                        ):
                            expansion = expand_deferred_event_understanding(
                                decision=understanding,
                                article=article,
                                event=event,
                                facts=article_facts,
                                topic=topic,
                                discovery=discovery,
                            )
                            if expansion is not None and getattr(expansion, "attempted", False):
                                stats["event_understanding_resolution_expansions"] += 1
                                queued_urls = {
                                    str(getattr(queued_candidate, "url", "") or "").strip()
                                    for queued_candidate in queue
                                }
                                appended = 0
                                for expanded_candidate in getattr(expansion, "candidates", ()):
                                    expanded_url = str(getattr(expanded_candidate, "url", "") or "").strip()
                                    if not expanded_url or expanded_url in seen_urls or expanded_url in queued_urls:
                                        continue
                                    queue.append(expanded_candidate)
                                    queued_urls.add(expanded_url)
                                    event_understanding_resolution_candidate_urls.add(expanded_url)
                                    appended += 1
                                stats["event_understanding_resolution_candidates"] += appended
                                attempts.append(_attempt(
                                    topic=topic.topic_id,
                                    query=query,
                                    domain=domain,
                                    stage="event_understanding_resolution",
                                    status="expanded" if appended else "defer",
                                    reason=str(getattr(expansion, "reason", "event_understanding_defer:resolution_unknown")),
                                ))
                        continue
                    if understanding.article_role is not ArticleEventRole.PRIMARY or not understanding.publishable_event:
                        attempts.append(_attempt(
                            topic=topic.topic_id,
                            query=query,
                            domain=domain,
                            stage="event_understanding",
                            status="skip",
                            reason=understanding.reasons[0] if understanding.reasons else "not_primary_event",
                        ))
                        continue

                    generation_request = GenerationRequest(event=event, facts=article_facts, evidence=article_evidence)
                    identity_text = generation_request.evidence_text
                    duplicate_event = False
                    identity_deferred = False
                    identity_facts = {**facts, **article_facts}
                    same_topic_priors = tuple(
                        prior for prior in published if prior.topic.topic_id == topic.topic_id
                    )
                    if same_topic_priors and local_verifier is None:
                        local_verifier = LocalNliVerifier.transformers_default()

                    for prior in same_topic_priors:
                        prior_event = events.get(prior.candidate.event_id)
                        if not isinstance(prior_event, CandidateEvent):
                            raise AssertionError("published candidate lost event identity provenance")
                        identity_stats["comparisons"] += 1
                        precheck = compare_candidate_identity(event, prior_event, identity_facts)
                        if precheck.deterministic_block:
                            identity_stats["deterministic_blocks"] += 1
                            continue
                        judgment = judge_same_event_mutual_entailment(
                            identity_text,
                            prior.identity_text,
                            primary=primary_verifier,
                            secondary=local_verifier,
                        )
                        identity_stats["secondary_checks"] += judgment.secondary_checks
                        identity_stats["primary_checks"] += judgment.primary_checks
                        if judgment.same_event is None:
                            identity_stats["unavailable"] += 1
                        elif judgment.same_event is False:
                            identity_stats["different_event"] += 1
                        resolution = resolve_candidate_pair(event, prior_event, identity_facts, semantic_same_event=judgment.same_event)
                        disposition = identity_disposition(resolution.decision)
                        if disposition is IdentityDisposition.DEFER:
                            resolution_judgment = None
                            if stats["identity_resolution_attempts"] < MAX_IDENTITY_DEFER_RESOLUTION_ATTEMPTS_PER_TOPIC:
                                stats["identity_resolution_attempts"] += 1
                                identity_stats["defer_resolution_attempts"] += 1
                                resolution_judgment = resolve_deferred_identity(
                                    event,
                                    prior_event,
                                    discovery=discovery,
                                    acquisition=acquisition,
                                    topic_id=topic.topic_id,
                                )
                            if resolution_judgment is not None and resolution_judgment.same_event is True:
                                identity_stats["same_event"] += 1
                                identity_stats["defer_resolution_same_event"] += 1
                                attempts.append(_attempt(
                                    topic=topic.topic_id,
                                    query=query,
                                    domain=domain,
                                    stage="event_identity",
                                    status="skip",
                                    reason="cross_source_same_event_resolved_by_source_expansion",
                                ))
                                duplicate_event = True
                                break
                            if resolution_judgment is not None and resolution_judgment.same_event is False:
                                identity_stats["different_event"] += 1
                                continue
                            identity_stats["deferred"] += 1
                            identity_stats["defer_resolution_held"] += 1
                            attempts.append(_attempt(
                                topic=topic.topic_id,
                                query=query,
                                domain=domain,
                                stage="event_identity",
                                status="defer",
                                reason="identity_unresolved",
                            ))
                            identity_deferred = True
                            break
                        if disposition is IdentityDisposition.SAME_EVENT:
                            identity_stats["same_event"] += 1
                            attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="event_identity", status="skip", reason="cross_source_same_event_already_published"))
                            duplicate_event = True
                            break
                    if duplicate_event or identity_deferred:
                        continue

                    assessment = phase6.assess_with_auto_material(
                        event,
                        facts=article_facts,
                        evidence=article_evidence,
                        selection_context=Phase6SelectionContext(topic_relevant=event_relevant, fresh=True, source_usable=True, identity_resolved=True),
                    )
                    if assessment.material.verdict is MaterialEventVerdict.MATERIAL:
                        stats["material_events"] += 1
                    if assessment.event_assessment.selection.verdict is not SelectionVerdict.INCLUDE:
                        continue
                    stats["included_events"] += 1
                    if stats["verification_attempts"] >= MAX_VERIFICATION_ATTEMPTS_PER_TOPIC:
                        break
                    stats["verification_attempts"] += 1

                    if local_verifier is None:
                        local_verifier = LocalNliVerifier.transformers_default()

                    entry_candidate = produce_phase7_entry_candidate(
                        generation_request,
                        primary_generator=generator,
                        primary_verifier=primary_verifier,
                        secondary_verifier=local_verifier,
                    )
                    if entry_candidate is None:
                        generation_stats["extractive_fallback_unavailable"] += 1
                        attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="generation", status="skip", reason="extractive_fallback_unavailable"))
                        continue

                    _record_generation_stats(entry_candidate, generation_stats, generation_route_stats)
                    _record_verification_stats(entry_candidate, verification_stats)
                    if not entry_candidate.publishable:
                        verdicts = {item.role.value: item.claim.verdict.value for item in entry_candidate.verification.claims}
                        attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="verification", status="skip", reason=";".join(f"{key}={value}" for key, value in sorted(verdicts.items())) or "not_publishable"))
                        continue

                    published.append(
                        PublishedCandidate(
                            topic=topic,
                            candidate=entry_candidate,
                            source_group_key=source_group_key,
                            content_sha256=content_sha256,
                            identity_text=identity_text,
                            source_identity_text=article.body,
                            source_url=article.provenance.url,
                        )
                    )
                    published_source_groups.add(source_group_key)
                    published_content_fingerprints.add(content_sha256)
                    stats["published_entries"] += 1
                    articles[article.article_id] = article
                    for item in semantic_result.evidence:
                        if item.evidence_id in generation_request.evidence_ids:
                            evidence[item.evidence_id] = item
                    for fact_id in event.fact_ids:
                        facts[fact_id] = article_facts[fact_id]
                    events[event.event_id] = event
                    for item in entry_candidate.verification.claims:
                        claims[item.claim.claim_id] = item.claim
                    attempts.append(_attempt(topic=topic.topic_id, query=query, domain=domain, stage="publish_gate", status="pass"))
                    break

    briefing_id = f"daily-{now.astimezone(KST).strftime('%Y%m%dT%H%M%S%z')}"
    rendered = build_rendered_briefing(briefing_id=briefing_id, generated_at=now.astimezone(KST), candidates=tuple(item.candidate for item in published))

    published_by_event = {item.candidate.event_id: item for item in published}
    rendered_sources: list[dict[str, str]] = []
    for entry in rendered.entries:
        source = published_by_event.get(entry.event_id)
        if source is None:
            raise AssertionError("rendered event lost production source provenance")
        rendered_sources.append(
            {
                "event_id": entry.event_id,
                "source_group_key": source.source_group_key,
                "content_sha256": source.content_sha256,
                "source_url": source.source_url,
                "render_mode": source.candidate.final_generation.render_mode.value,
                "verification_recovery_reason": source.candidate.verification_recovery_reason.value if source.candidate.verification_recovery_reason is not None else "",
            }
        )

    publish = bool(rendered.entries)
    html_sha256: str | None = None
    html_bytes = 0
    if publish:
        bundle = ContractBundle(
            articles=tuple(articles.values()),
            evidence=tuple(evidence.values()),
            facts=tuple(facts.values()),
            events=tuple(events.values()),
            claims=tuple(claims.values()),
            briefing=rendered,
        )
        bundle.validate()
        topic_by_event = {item.candidate.event_id: item.topic.name for item in published}
        source_by_event = {item.candidate.event_id: item.source_url for item in published}
        view = build_briefing_view_model(
            rendered,
            topic_by_event=topic_by_event,
            source_by_event=source_by_event,
        )
        push_worker_url = os.environ.get("PUSH_WORKER_URL", "").strip() or None
        html = render_briefing_html(view, runtime=PwaRuntimeConfig(push_worker_url=push_worker_url))
        if "key-fact-panel" in html or "next-signal" in html or "검색 관심 흐름" in html:
            raise AssertionError("production renderer manufactured unsupported UI data")
        stage_site(output_dir, html)
        html_bytes = len(html.encode("utf-8"))
        html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

    primary_route_stats = getattr(primary_verifier, "route_stats", {})
    verification_stats["primary_failover_routes"] = primary_route_stats  # type: ignore[assignment]
    verification_stats["identity_local"] = {"checks": identity_stats["secondary_checks"]}
    acquisition_stats["configured_methods"] = {  # type: ignore[assignment]
        f"{acquisition.fetcher.method_id}+{acquisition.primary_extractor.method_id}": 1,
        f"{acquisition.fetcher.method_id}+{acquisition.fallback_extractor.method_id}": 1,
        f"{acquisition.fallback_renderer.method_id}+{acquisition.primary_extractor.method_id}": 1 if acquisition.fallback_renderer is not None else 0,
        f"{acquisition.fallback_renderer.method_id}+{acquisition.fallback_extractor.method_id}": 1 if acquisition.fallback_renderer is not None else 0,
    }
    tool_usage = {
        "discovery": discovery.route_stats,
        "acquisition": acquisition_stats,
        "fact_extraction": extractor.route_stats,
        "generation": generation_route_stats,
        "verification": verification_stats,
        "identity": identity_stats,
    }

    state = {
        "status": "SUCCESS" if publish else "NO_PUBLISHABLE_ITEMS",
        "publish": publish,
        "briefing_id": briefing_id,
        "generated_at": now.astimezone(KST).isoformat(),
        "published_entries": len(rendered.entries),
        "topic_count": len(topics),
        "html_sha256": html_sha256,
        "html_bytes": html_bytes,
    }
    audit = {
        "status": state["status"],
        "publish": publish,
        "topic_stats": topic_stats,
        "attempts": attempts,
        "generation_stats": generation_stats,
        "identity_stats": identity_stats,
        "tool_usage": tool_usage,
        "rendered_sources": rendered_sources,
        "provider_roles": {
            "generation": GROQ_20B,
            "primary_verifier": CLOUDFLARE_MODEL,
            "secondary_verifier": LOCAL_NLI_MODEL,
            "groq_configured": generator is not None,
        },
        "paid_paths": 0,
        "article_body_logged": False,
        "headline_or_summary_logged": False,
        "secrets_logged": False,
    }
    _write_json(state_path, state)
    _write_json(audit_path, audit)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", default="config/topics.json")
    parser.add_argument("--output", default="build/site")
    parser.add_argument("--state", default="build/run-state.json")
    parser.add_argument("--audit", default="build/production-audit.json")
    args = parser.parse_args()

    state_path = Path(args.state)
    audit_path = Path(args.audit)
    try:
        state = run_production(topics_path=Path(args.topics), output_dir=Path(args.output), state_path=state_path, audit_path=audit_path)
    except Exception as exc:
        failure = {"status": "TOTAL_FAILURE", "publish": False, "error_type": type(exc).__name__}
        _write_json(state_path, failure)
        _write_json(
            audit_path,
            {
                **failure,
                "paid_paths": 0,
                "article_body_logged": False,
                "headline_or_summary_logged": False,
                "secrets_logged": False,
            },
        )
        raise

    print(
        "PHASE11_PRODUCTION_RUN "
        f"status={state['status']} publish={str(state['publish']).lower()} "
        f"entries={state['published_entries']}"
    )


if __name__ == "__main__":
    main()
