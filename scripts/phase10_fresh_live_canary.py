from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from insight_desk.acquisition import (
    AcquisitionError,
    AcquisitionPipeline,
    ArticleCandidate,
    PlaywrightHtmlRenderer,
    TrafilaturaExtractor,
    UrlLibHtmlFetcher,
    normalize_naver_items,
)
from insight_desk.api import NaverApiClient
from insight_desk.api.naver import NaverCredentials
from insight_desk.core import ContractBundle, SelectionVerdict
from insight_desk.generation import GenerationRequest, Groq20BBriefingGenerator
from insight_desk.phase7 import produce_phase7_entry_candidate
from insight_desk.providers.cloudflare import CLOUDFLARE_MODEL, CloudflareClaimVerifier
from insight_desk.providers.groq import GROQ_20B, GROQ_120B, GroqFreeClient
from insight_desk.providers.local_nli import LOCAL_NLI_MODEL, LocalNliVerifier
from insight_desk.rendering import build_rendered_briefing
from insight_desk.semantic import (
    KiwiDeterministicFactExtractor,
    Phase6EventEngine,
    Phase6SelectionContext,
    SemanticPipeline,
)
from insight_desk.semantic.material import MaterialEventVerdict, assess_material_event
from insight_desk.ui import build_briefing_view_model, render_briefing_html


TOPIC_ID = "ai_tech"
QUERIES = ("인공지능 발표", "AI 투자 발표", "AI 출시")
MAX_ACQUISITION_ATTEMPTS = 8
FRESHNESS_WINDOW = timedelta(hours=72)
FUTURE_CLOCK_TOLERANCE = timedelta(hours=6)
KST = timezone(timedelta(hours=9))


def _alternate_candidate(raw: dict[str, object], original: ArticleCandidate) -> ArticleCandidate | None:
    link = str(raw.get("link") or "").strip()
    if not link or link == original.url:
        return None
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return ArticleCandidate(
        candidate_id=original.candidate_id + "-alt",
        url=link,
        search_title=original.search_title,
        source_name=(parsed.hostname or parsed.netloc).lower(),
        published_at=original.published_at,
        topic_ids=original.topic_ids,
        query=original.query,
        retrieved_via="naver_search_alternate_link",
    )


def _is_fresh(published_at: datetime | None, now: datetime) -> bool | None:
    if published_at is None:
        return None
    age = now.astimezone(timezone.utc) - published_at.astimezone(timezone.utc)
    return -FUTURE_CLOCK_TOLERANCE <= age <= FRESHNESS_WINDOW


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "unknown").lower()


def _candidate_queue(
    payload: dict[str, object],
    candidates: tuple[ArticleCandidate, ...],
) -> list[ArticleCandidate]:
    raw_items = payload.get("items", [])
    raw_by_original: dict[str, dict[str, object]] = {}
    if isinstance(raw_items, list):
        for raw in raw_items:
            if isinstance(raw, dict):
                original = str(raw.get("originallink") or raw.get("link") or "").strip()
                if original:
                    raw_by_original[original] = raw

    queue: list[ArticleCandidate] = []
    for candidate in candidates:
        queue.append(candidate)
        raw = raw_by_original.get(candidate.url)
        if raw is not None:
            alternate = _alternate_candidate(raw, candidate)
            if alternate is not None:
                queue.append(alternate)
    return queue


def _safe_attempt(
    *,
    query: str,
    domain: str,
    route: str,
    stage: str,
    status: str,
    reason: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "query": query,
        "domain": domain,
        "route": route,
        "stage": stage,
        "status": status,
    }
    if reason is not None:
        result["reason"] = reason
    return result


def main() -> None:
    naver_credentials = NaverCredentials.from_environment()
    if naver_credentials is None:
        raise RuntimeError("NAVER credentials unavailable")

    naver = NaverApiClient(naver_credentials)
    acquisition = AcquisitionPipeline(
        fetcher=UrlLibHtmlFetcher(timeout=15),
        primary_extractor=TrafilaturaExtractor(),
        fallback_renderer=PlaywrightHtmlRenderer(timeout_ms=20_000),
    )
    semantic = SemanticPipeline()
    extractor = KiwiDeterministicFactExtractor()
    phase6 = Phase6EventEngine()

    # Provider clients are frozen to their Phase 6/7 roles. They are instantiated once and reused.
    temporal_auxiliary = GroqFreeClient.from_env(GROQ_120B)
    generator = Groq20BBriefingGenerator(GroqFreeClient.from_env(GROQ_20B))
    primary_verifier = CloudflareClaimVerifier.from_env()

    now = datetime.now(timezone.utc)
    attempts: list[dict[str, object]] = []
    acquisition_attempts = 0
    acquired_articles = 0
    semantic_events = 0
    material_events = 0
    included_events = 0
    success: dict[str, object] | None = None
    seen_urls: set[str] = set()
    local_verifier: LocalNliVerifier | None = None

    for query in QUERIES:
        if acquisition_attempts >= MAX_ACQUISITION_ATTEMPTS or success is not None:
            break
        payload = naver.search_news(query, display=10, start=1, sort="date")
        candidates = normalize_naver_items(payload, topic_id=TOPIC_ID, query=query)
        queue = _candidate_queue(payload, candidates)

        for candidate in queue:
            if acquisition_attempts >= MAX_ACQUISITION_ATTEMPTS or success is not None:
                break
            if candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            acquisition_attempts += 1
            domain = _domain(candidate.url)

            try:
                acquired = acquisition.acquire(candidate)
            except AcquisitionError as exc:
                attempts.append(
                    _safe_attempt(
                        query=query,
                        domain=domain,
                        route=candidate.retrieved_via,
                        stage="acquisition",
                        status="skip",
                        reason=exc.failure_kind.value,
                    )
                )
                continue

            acquired_articles += 1
            article = acquired.article
            fresh = _is_fresh(article.provenance.published_at, now)
            if fresh is not True:
                attempts.append(
                    _safe_attempt(
                        query=query,
                        domain=domain,
                        route=candidate.retrieved_via,
                        stage="freshness",
                        status="skip",
                        reason="published_at_missing" if fresh is None else "outside_72h_window",
                    )
                )
                continue

            semantic_result = semantic.extract_article(
                article,
                topic_id=TOPIC_ID,
                extractor=extractor,
            )
            if not semantic_result.events:
                attempts.append(
                    _safe_attempt(
                        query=query,
                        domain=domain,
                        route=candidate.retrieved_via,
                        stage="semantic",
                        status="skip",
                        reason="no_deterministic_fact",
                    )
                )
                continue

            facts = {fact.fact_id: fact for fact in semantic_result.facts}
            evidence = {span.evidence_id: span for span in semantic_result.evidence}
            semantic_events += len(semantic_result.events)

            for event in semantic_result.events:
                material = assess_material_event(event, facts=facts, evidence=evidence)
                if material.verdict is not MaterialEventVerdict.MATERIAL:
                    continue
                material_events += 1

                assessment = phase6.assess_with_auto_material(
                    event,
                    facts=facts,
                    evidence=evidence,
                    selection_context=Phase6SelectionContext(
                        topic_relevant=TOPIC_ID in article.topic_ids,
                        fresh=True,
                        source_usable=True,
                        # This canary preserves one extracted candidate as a separate event and does
                        # not perform any cross-candidate merge. No ambiguous merge is being asserted.
                        identity_resolved=True,
                    ),
                    temporal_auxiliary=temporal_auxiliary,
                )
                if assessment.event_assessment.selection.verdict is not SelectionVerdict.INCLUDE:
                    continue
                included_events += 1

                generation_request = GenerationRequest(
                    event=event,
                    facts=facts,
                    evidence=evidence,
                )

                # Defer the heavyweight local verifier until a real event reaches the publish gate.
                if local_verifier is None:
                    local_verifier = LocalNliVerifier.transformers_default()

                entry_candidate = produce_phase7_entry_candidate(
                    generation_request,
                    primary_generator=generator,
                    primary_verifier=primary_verifier,
                    secondary_verifier=local_verifier,
                )
                if not entry_candidate.publishable:
                    verdicts = {
                        item.role.value: item.claim.verdict.value
                        for item in entry_candidate.verification.claims
                    }
                    attempts.append(
                        _safe_attempt(
                            query=query,
                            domain=domain,
                            route=candidate.retrieved_via,
                            stage="verification",
                            status="skip",
                            reason=";".join(f"{key}={value}" for key, value in sorted(verdicts.items()))
                            or "preservation_rejected",
                        )
                    )
                    continue

                rendered = build_rendered_briefing(
                    briefing_id=f"live-{now.astimezone(KST).strftime('%Y%m%dT%H%M%S%z')}",
                    generated_at=now.astimezone(KST),
                    candidates=(entry_candidate,),
                )
                if len(rendered.entries) != 1:
                    raise AssertionError("publishable live candidate did not produce exactly one entry")

                claims = tuple(item.claim for item in entry_candidate.verification.claims)
                bundle = ContractBundle(
                    articles=(article,),
                    evidence=semantic_result.evidence,
                    facts=semantic_result.facts,
                    events=(event,),
                    claims=claims,
                    briefing=rendered,
                )
                bundle.validate()

                view = build_briefing_view_model(rendered, topic_by_event={event.event_id: TOPIC_ID})
                html = render_briefing_html(view)
                if "key-fact-panel" in html or "next-signal" in html or "검색 관심 흐름" in html:
                    raise AssertionError("live renderer manufactured an unsupported UI slot")
                if "manifest.webmanifest" not in html:
                    raise AssertionError("live renderer lost PWA manifest link")

                claim_verdicts = {
                    item.role.value: item.claim.verdict.value
                    for item in entry_candidate.verification.claims
                }
                temporal_sources = [item.source.value for item in assessment.event_assessment.temporal]
                success = {
                    "query": query,
                    "domain": domain,
                    "route": candidate.retrieved_via,
                    "extraction_method": acquired.extraction_method,
                    "fallback_used": acquired.fallback_used,
                    "article_id": article.article_id,
                    "event_id": event.event_id,
                    "fact_count": len(event.fact_ids),
                    "evidence_count": len(generation_request.evidence_ids),
                    "material_verdict": assessment.material.verdict.value,
                    "selection_verdict": assessment.event_assessment.selection.verdict.value,
                    "temporal_sources": temporal_sources,
                    "generation_render_mode": entry_candidate.final_generation.render_mode.value,
                    "preservation_accepted": entry_candidate.verification.preservation.accepted,
                    "claim_verdicts": claim_verdicts,
                    "groq_generation_model": GROQ_20B,
                    "groq_temporal_model": GROQ_120B,
                    "cloudflare_model": CLOUDFLARE_MODEL,
                    "local_nli_model": LOCAL_NLI_MODEL,
                    "rendered_entries": len(rendered.entries),
                    "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                    "html_bytes": len(html.encode("utf-8")),
                    "contract_bundle_valid": True,
                }
                attempts.append(
                    _safe_attempt(
                        query=query,
                        domain=domain,
                        route=candidate.retrieved_via,
                        stage="end_to_end",
                        status="pass",
                    )
                )
                break

            if success is None and material_events == 0:
                attempts.append(
                    _safe_attempt(
                        query=query,
                        domain=domain,
                        route=candidate.retrieved_via,
                        stage="material",
                        status="skip",
                        reason="no_material_event_in_article",
                    )
                )

    report = {
        "status": "pass" if success is not None else "fail",
        "topic_id": TOPIC_ID,
        "query_count": len(QUERIES),
        "max_acquisition_attempts": MAX_ACQUISITION_ATTEMPTS,
        "acquisition_attempts": acquisition_attempts,
        "acquired_articles": acquired_articles,
        "semantic_events": semantic_events,
        "material_events": material_events,
        "included_events": included_events,
        "attempts": attempts,
        "success": success,
        "secrets_logged": False,
        "article_body_logged": False,
        "headline_or_summary_logged": False,
        "paid_paths": 0,
    }
    print("PHASE10_FRESH_LIVE_CANARY")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if success is None:
        raise AssertionError("no bounded live article completed the current Phase 5-8 publish path")


if __name__ == "__main__":
    main()
