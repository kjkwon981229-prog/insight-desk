# Insight Desk — Orchestration Contract V2

Status: `PHASE_2_SINGLE_OWNER_FROZEN / PHASE_3_DATA_CONTRACT_FROZEN / PHASE_4_PROVIDER_AND_MIGRATION_GATED`
Date: 2026-08-27

This contract supersedes Architecture Freeze V1 only for the next production migration. V1 remains historical evidence of the previous clean-room architecture. This V2 freeze does not rewire the active Phase 11 production path by itself.

## 1. Product objective

Insight Desk exists to:

1. discover enough fresh articles relevant to the configured user interests;
2. acquire the real source article and provenance;
3. understand the event accurately;
4. enrich only when authoritative facts are useful;
5. resolve same-event and parent-child identity;
6. express the established event as a headline and summary;
7. verify the final claims against source and established facts;
8. enforce a mechanical publication contract;
9. render the verified publication in the PWA;
10. notify the user when a new verified briefing is actually published.

The orchestrator coordinates these owners. It is not a central semantic judge.

## 2. Single-owner map

| Responsibility | Single owner | Input | Output | Must not decide |
| --- | --- | --- | --- | --- |
| Discovery | `news_discovery` | TopicQuery | ArticleCandidate | relevance, event meaning, identity, verification |
| Source | `source_acquisition` | ArticleCandidate | SourceDocument | relevance, event meaning, identity, verification |
| Relevance | `relevance_engine` | SourceDocument | RelevanceDecision | event meaning, identity, generation, verification |
| Event understanding | `canonical_event_builder` | RelevantSourceSet | CanonicalEventDraft | publication selection, identity, generation, verification |
| Authoritative enrichment | `authoritative_enricher` | CanonicalEventDraft | EnrichedEventFacts | relevance, identity, generation, verification |
| Event identity | `canonical_identity_engine` | CanonicalEventDraftSet | CanonicalEvent | relevance, story quality, generation, verification |
| Generation | `publication_generator` | CanonicalEvent | PublicationDraft | relevance, identity, authoritative fact invention, verification |
| Verification | `claim_verification_engine` | PublicationDraft + CanonicalEvent | VerifiedClaims | relevance, identity, dedupe, generation |
| Publication contract | `publication_contract` | CanonicalEvent + VerifiedClaims | VerifiedPublication | all semantic judgments |
| Rendering | `pwa_renderer` | VerifiedPublicationSet | PwaArtifact | all semantic judgments |
| Push | `push_dispatcher` | PublishedBriefingState | PushDeliveryState | all semantic judgments |
| Execution | `github_actions_orchestrator` | ProductionTrigger | PipelineExecutionState | all semantic judgments |

The machine-readable form is `insight_desk/core/orchestration_v2.py`.

## 3. Shared object path

The migration target is:

`ArticleCandidate -> SourceDocument -> CanonicalEvent -> VerifiedPublication`

`CanonicalEvent` is the semantic source of truth after event identity resolution. Downstream stages may add verification or presentation state, but they must not reinterpret the event from raw article text and silently change actor, action, time, metric, attribution, source identity, or parent-child identity.

## 4. CanonicalEvent contract

Required fields:

- `event_id`
- `topic`
- `actor`
- `action`
- `event_type`
- `source_ids`

Supported semantic fields:

- `object`
- `event_time`
- `publication_time`
- `participants`
- `metric`
- `unit`
- `value`
- `attribution`
- `parent_event_id`
- `authoritative_fact_ids`

Rules:

- source provenance is never optional for a canonical event;
- an event cannot be its own parent;
- parent-child identity is explicit, not reconstructed from headline similarity;
- `metric` and `value` travel together;
- event time is an ISO-8601 date or offset-aware datetime when known;
- authoritative facts are references to facts returned by the authoritative enrichment owner, not LLM-created substitutes.

## 5. SourceDocument contract

A SourceDocument binds the source used for event understanding to:

- discovery candidate id(s);
- publisher;
- source URL;
- exact title/body;
- fetched time;
- article publication time when known;
- retrieval method;
- SHA-256 body digest.

The digest exists so replay and verification can prove they used the same source bytes.

## 6. AuthoritativeFact contract

Authoritative facts carry:

- stable fact id;
- provider id such as ECOS, KOSIS, OpenDART, or another approved official source;
- subject / predicate / value;
- optional unit and effective time;
- retrieval time;
- authoritative source URL.

The authoritative owner enriches an event only when needed. It does not replace article discovery, event understanding, identity, or claim verification.

## 7. VerifiedPublication contract

A VerifiedPublication preserves the established canonical identity while adding final presentation and verification references:

- `publication_id`
- `event_id`
- `topic`
- `headline`
- `summary`
- `source_ids`
- `primary_source_url`
- `claim_ids`
- `verification_check_ids`
- `verified_at`
- `render_mode`
- `event_time`
- `publication_time`
- `parent_event_id`
- `authoritative_fact_ids`

The publication contract may validate URLs, timestamps, IDs, required fields, provenance links, and the presence of verification. It may not decide whether an article is relevant, whether two events are the same, whether prose is a good story, or whether a claim is semantically supported.

## 8. Identity and dedupe rule

Only `canonical_identity_engine` owns same-event / distinct-event / parent-child decisions.

Source URL equality, content hashes, normalized headline equality, and normalized summary equality remain valid mechanical duplicate guards for exact artifacts or source aliases. They must not be promoted into semantic same-event authority.

Headline similarity and visible-text rules may be used only as candidate retrieval or diagnostics once Phase 4 begins. They cannot be publication-level semantic judges.

## 9. Uncertainty resolution

Uncertainty is resolved before dropping an otherwise relevant candidate:

`additional source -> authoritative enrichment when applicable -> semantic reassessment -> claim verification -> final hold only if unresolved`

Recall must not be purchased by accepting unsupported claims, and precision must not be purchased by making broad semantic drop rules the primary strategy.

## 10. Test architecture target

After Phase 4 rewiring, the only acceptance hierarchy is:

1. Unit tests for each single-owner contract.
2. Production replay using preserved real source input and the same production functions.
3. One fresh canary after unit + replay are green.
4. Human/source/render audit as an acceptance test of the integrated pipeline.

Historic visible-card regression fixtures remain useful evidence but are not sufficient production replay because they do not contain the original complete source/fact state for every card.

## 11. PHASE 4 migration gate

Provider qualification is necessary but not sufficient for production rewiring.

`config/event_understanding_migration_gate_v2.json` mechanically freezes the currently reachable legacy bypasses. Production rewiring remains closed while any of these are active:

1. `CandidateEvent -> CanonicalEvent` direct compatibility lift via `canonical_event_from_candidate()`;
2. canonical identity reading `SourceDocument.body` and reinterpreting raw source after event understanding;
3. legacy `CandidateEvent` identity comparison remaining an authority inside the compatibility identity path.

The gate additionally requires a selected Event Understanding provider with `MINIMUM_COMPATIBILITY_PASS`, source-range-bound Event Understanding output, and an identity path that consumes canonical event drafts without raw-source reinterpretation.

Current provider state is separately frozen in `config/event_understanding_provider_status_v2.json`. Mistral Large 3 is only a qualification candidate and is currently `QUALIFICATION_BLOCKED_CREDENTIAL` because GitHub Actions has no configured `MISTRAL_API_KEY`. It is not selected and production is not wired.

A future provider PASS must not silently open production. The migration blockers must first be removed and the migration gate explicitly opened.

## 12. Migration boundary

During PHASE 2 and PHASE 3:

- no detector is added for a new live sentence family;
- no production marker is created;
- no canonical live is run;
- active production behavior is intentionally unchanged;
- V2 contracts are introduced in parallel and tested independently.

PHASE 4 may proceed only from the frozen owner map and data contract. Its job is removal of bypass semantic authorities and rewiring of the active production path, not further detector accumulation.

While the provider inventory is blocked or the PHASE 4 migration gate is closed:

- no production Event Understanding rewiring is authorized;
- no production marker or fresh canonical live is authorized;
- no deploy or Push acceptance is authorized;
- compatibility replay success must not be represented as new-architecture Phase 5/6 completion.
