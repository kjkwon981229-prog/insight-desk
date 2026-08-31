# Phase 1 — Production Runtime Graph Freeze

Status: **COMPLETE / READ-ONLY AUDIT**

This document freezes the actual runtime wiring observed on PR #84 before any Phase 2–4 architecture rewrite. It is not a claim that the current architecture is correct or merge-ready.

## 0. Scope and non-goals

Phase 1 answers only: **what actually runs in production, in what order, with which owners, fallbacks, contracts, and data transformations?**

No detector tuning, provider tuning, fresh live, deploy, Push, or merge is authorized by this document.

Target architecture remains:

`Discovery -> Source -> Relevance -> Event Understanding -> Authoritative Enrichment -> Canonical Event Identity -> Generation -> Verification -> Publication Contract -> PWA -> Push`

Common target objects remain:

`ArticleCandidate -> SourceDocument -> CanonicalEvent -> VerifiedPublication`

---

## 1. Actual production entrypoint

GitHub Actions production workflow executes `scripts/phase11_daily_production.py`.

That entrypoint runs the legacy mechanical loop under `production_v2_runtime(...)`, which temporarily patches runtime owners and restores the ordinary module contract on exit.

Key files:

- `.github/workflows/insight-desk-production.yml`
- `scripts/phase11_daily_production.py`
- `insight_desk/production_runtime_v2.py`
- `insight_desk/production_orchestrator_v2.py`
- `scripts/phase11_daily_production_core.py`

The important distinction is **legacy iterator != legacy semantic authority**. The loop remains legacy-shaped, but several hooks are replaced inside the execution scope.

---

## 2. Runtime graph — actual current path

```text
GitHub Actions
  -> scripts/phase11_daily_production.py
  -> production_v2_runtime(core)

Discovery
  -> default_news_discovery()
  -> Naver + Bing RSS + GDELT candidate routes

Source acquisition
  -> HTTP fetch + Trafilatura
  -> HTTP fetch + deterministic article/main extraction
  -> Playwright render + Trafilatura
  -> Playwright render + deterministic article/main extraction
  -> RawArticle
  -> SourceDocument registry binding

Relevance
  -> source-level configured-literal preselection (topic_relevant)
  -> configured evidence-local event relevance owner
  -> no visible-story semantic re-admission in production

Event understanding — CURRENT PRODUCTION TRUTH
  -> LegacySemanticPipeline.extract_article()
  -> EvidenceSpan + EventFact + CandidateEvent
  -> article-scope Event Understanding owner
  -> resolved PRIMARY only
  -> CanonicalEventDraft with exact source ranges
  -> CanonicalEvent

Authoritative enrichment
  -> AuthoritativeEnricher
  -> conditional ECOS / KOSIS / OpenDART lookups
  -> AuthoritativeFact ids bound to CanonicalEvent

Phase 6 mechanics
  -> EvidenceIntegrityPhase6EventEngine
  -> evidence-integrity/material signal only
  -> consumes existing CanonicalEvent temporal/identity state
  -> selection mechanics only; no EventFact semantic reinterpretation

Visible projection
  -> exactly one canonical evidence proposition is required
  -> headline == summary == immutable source range bytes
  -> provider generation is not called

Verification
  -> deterministic full-proposition source proof
  -> external semantic verifier is not called on the visible path
  -> Local NLI independent second confirmation after logical primary support
  -> SUPPORTED only when required verification contract passes

Identity / dedupe
  -> CanonicalIdentityEngine owner wrapper
  -> BOK parent/child special path
  -> source fingerprint auxiliary
  -> legacy semantic same-event judgment using verification-family providers
  -> exact normalized headline/summary duplicate gates still remain in mechanical loop

Publication
  -> VerifiedPublication built only from supported Phase7 candidate
  -> headline/summary copied from final GeneratedDraft
  -> PublicationIdentityManifest + SHA-256 digest

PWA
  -> RenderedBriefing
  -> StoryViewModel(headline, summary, source_url, topic, render_mode)
  -> HTML renderer

Push
  -> publication digest bound notification gateway
  -> idempotency based on publication digest
```

---

## 3. Provider / credential truth

### Generation

- Groq GPT-OSS 20B is the actual configured primary generation role.
- Gemini is the zero-cost alternate generation path when configured.
- Groq GPT-OSS 120B is defined as a temporal auxiliary role, but the current daily production call does **not** pass a temporal auxiliary. Therefore 120B is not part of the active daily production call path.

### Verification

- Cloudflare is first logical primary.
- Gemini is failover only when the Cloudflare logical-primary route cannot return a determinate result.
- Local NLI is not an outage fallback; it is an independent second confirmation in the supported path.

### Event Understanding V5 provider state

No V5-qualified LLM provider is selected.

Current status remains:

```text
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
```

Therefore current production Event Understanding is still the legacy semantic extraction bridge, not a hidden V5 provider fallback.

### Authoritative APIs

The PR-head workflow references ECOS, KOSIS, and OpenDART credentials. Runtime clients are conditional: missing key means enrichment miss / client unavailable, not event rejection.

The last proven successful main production live established the then-required Naver/Groq/Cloudflare credential gate. ECOS/KOSIS/OpenDART same-head live credential presence has not been proven because PR live build/deploy is intentionally blocked.

---

## 4. Relevance — exact current ownership

The core file contains both source-level and event-level relevance functions, but Canonical V2 runtime changes the authority:

1. `topic_relevant(title, body, topic)` remains as the source-level configured-literal preselection owner.
2. `event_topic_relevant(...)` is patched in production to only verify `CanonicalEvent.topic == topic.topic_id`.
3. visible topic/headline and visible story-quality semantic gates are disabled as semantic authorities in V2 production.

Consequence: current production does **not** semantically re-decide relevance at multiple later stages. The residual concern is that the source-level owner is still a configured literal matcher, which is a Phase 2 responsibility/quality issue, not a Phase 1 ambiguity.

---

## 5. Phase 6 selection / drop / defer truth

The generic selection contract supports:

- `INCLUDE`
- `EXCLUDE`
- `DEFER`

with explicit reasons for topic, materiality, freshness, source usability, identity, and missing signals.

However current daily production enters Phase 6 only after earlier hard gates have already established freshness/source/topic and uses `EvidenceIntegrityPhase6EventEngine`.

Important runtime behavior:

- the outer loop first runs the same mechanical evidence-integrity assessment and silently `continue`s if it is not `MATERIAL`;
- Phase 6 then repeats the evidence-integrity assessment through the scoped bridge;
- the supplied selection context is `topic_relevant=True`, `fresh=True`, `source_usable=True`, `identity_resolved=True` for the surviving candidate;
- therefore Phase 6 is effectively an INCLUDE/pass-through for structurally intact survivors;
- there is **no production hold queue or active uncertainty-resolution workflow** attached to the generic `DEFER` verdict in this daily loop.

This is an architectural gap relative to the target principle that unresolved uncertainty should be escalated/resolved rather than primarily discarded.

---

## 6. EventFact -> CanonicalEvent information loss

Current bridge is intentionally thin and requires one pre-identity EventFact per CandidateEvent.

EventFact contains information including:

- `fact_id`
- `evidence_ids`
- `subject`
- `action`
- `object`
- `temporal_state`
- `certainty`
- `polarity`
- `event_date`
- `location`
- `cause`
- `participants`

Current CanonicalEvent lift preserves actor/action/object, event date when ISO-resolved, participants, source identity, and later authority/parent links.

The bridge does not preserve as first-class CanonicalEvent fields:

- original `fact_id`
- original `evidence_ids`
- `temporal_state`
- `certainty`
- `polarity`
- `location`
- `cause`

This is a structural Phase 3 contract issue.

---

## 7. Identity / dedupe actual payload and authority

The current CanonicalIdentityEngine is the runtime wrapper owner, but it still delegates one important semantic decision to legacy machinery.

Order observed:

1. topic-local prior publication comparison;
2. source/visible fingerprint auxiliary paths;
3. deterministic candidate identity precheck;
4. semantic same-event judgment over evidence/source identity text;
5. pair resolution;
6. later normalized headline exact duplicate gate;
7. later normalized summary exact duplicate gate.

The semantic same-event judgment receives `primary_verifier` and `secondary_verifier`, i.e. the verification-family providers are reused for dedupe/identity judgment.

This violates the target responsibility boundary:

> Verification verifies source/claim support. Identity owns same-event / different-event / parent-child.

Removing this collision is a Phase 2–4 structural task.

---

## 8. Generation fallback and oversized-body leakage audit

### Hard generation contract

`GeneratedDraft` currently enforces:

- headline <= 120 chars
- summary <= 420 chars
- non-empty evidence ids

### Exact-source fallback

Fallback order is:

```text
Groq 20B primary (up to 2)
  -> Gemini free alternate (1)
  -> ExtractiveFallbackGenerator
```

The extractive fallback:

- uses cited evidence spans, not arbitrary article bytes;
- bounds summary to the same 420-char ceiling;
- chooses sentence / line / clause boundaries rather than raw character clipping;
- may still produce a long exact-source excerpt up to the ceiling.

### PWA leakage check

Current Canonical V2 publication builds `VerifiedPublication.summary` from `candidate.final_generation.draft.summary` only.

`StoryViewModel` receives only:

- headline
- summary
- topic
- source_url
- render_mode

The PWA renderer has no `SourceDocument.body` field to render.

Therefore a multi-thousand-character article body such as the observed historical bad UI state cannot be produced by the current normal `GeneratedDraft -> VerifiedPublication -> StoryViewModel` path without violating the hard summary contract.

Current conclusion:

- **raw body direct-to-PWA bypass: not found on this head**;
- **oversized current normal summary >420: structurally rejected**;
- historical screenshot state is therefore likely from an older publication/runtime artifact or a now-removed path, unless future evidence proves otherwise;
- exact-source fallback can still generate a visually excessive ~420-char source excerpt and should be redesigned on semantic/product grounds in Phase 4 rather than patched with article-specific detectors.

### Acceptance regression to preserve

The historical failure class must become a source-backed regression:

```text
Given a long article body,
publication must contain a compact standalone event summary,
not the article body,
not a clipped body prefix,
with source URL preserved and all visible claims supported.
```

The regression must test architecture, not the specific dance/performance article wording.

---

## 9. Replay truth

Historical production replay calls the same public production entrypoint and therefore exercises the same orchestration/semantic/identity/generation-policy/verification-policy/publication/PWA code path while replacing recorded external edges.

It is not equivalent to a fresh live:

- external providers are replayed, not called live;
- authoritative APIs are not proven by replay;
- historical artifacts do not always contain full raw article bodies, so some replay is exact-source excerpt level rather than full acquisition-body replay.

Use replay for deterministic regression closure, then a single fresh canary only after structural gates are closed.

---

## 10. Publication -> PWA -> Push binding

`VerifiedPublication` is the publication semantic boundary.

PWA receives the verified headline/summary and source URL without reinterpreting news meaning.

`PublicationIdentityManifest` binds publication/event/source/claim/check/parent/time/authority identities and produces a SHA-256 publication digest.

Push uses briefing/publication digest identity for idempotency. A repeated identical publication set does not create a new semantic publication identity; a changed digest is treated as an update.

---

## 11. Historical Phase 1 findings — current disposition

### Resolved — Event Understanding production gap

No provider is selected, but production no longer directly lifts `CandidateEvent`. The deterministic article-scope owner is explicit and promotes only resolved PRIMARY output through `CanonicalEventDraft`.

### Resolved for visible publication — CanonicalEvent information loss

Exact canonical evidence ranges, certainty, temporal state, polarity, location, cause, participants, and fact lineage cross the boundary. Visible semantics use the exact source proposition rather than the flat projection.

### Resolved — Identity/verifier responsibility collision

Canonical identity executes before Phase 6/7 and does not consume claim verifiers or generated visible text.

### Bounded — uncertainty resolution

Relevance, Event Understanding, and Identity each have bounded source-expansion lanes. Unresolved centrality or multi-proposition authority remains non-publishable rather than being guessed.

### Resolved for semantic integrity — exact-source visible authority

Production requires one complete canonical proposition and proves byte equality deterministically. Length or journalistic polish is a P2/P3 presentation concern and cannot truncate the proposition or reopen semantic authority.

### P2 — Residual mechanical duplication

Evidence-integrity material assessment is executed before Phase 6 and again inside the production-scoped Phase6 bridge. It is the same mechanical owner/logic, not conflicting semantics, but the duplicate check is removable architecture debt.

### P2 — Source-level relevance is still literal-config driven

Relevance is no longer repeatedly re-judged downstream, but the remaining source-level owner is configured-literal matching rather than a richer explicit RelevanceDecision contract.

---

## 12. Phase 1 completion gate

All requested runtime-map questions are now answered:

1. active discovery route — mapped;
2. provider/credential state — mapped with same-head limitations explicit;
3. where each API is called — mapped;
4. Groq 20B / 120B actual roles — mapped;
5. Cloudflare / Gemini failover / Local NLI order — mapped;
6. ECOS/KOSIS/OpenDART production wiring — mapped;
7. where EventFact is created and where information is lost — mapped;
8. actual dedupe payload/owners — mapped;
9. fallback tree — mapped;
10. production/replay function relationship — mapped;
11. publication -> PWA transformations — mapped;
12. Push binding to publication state — mapped.

**PHASE 1 = COMPLETE.**

This does not authorize fresh live or merge.

---

## 13. Next permitted work — Phase 2 only

Phase 2 must freeze **one owner per semantic responsibility** before code removal/rewrite:

```text
Discovery owner
Source acquisition owner
Relevance owner
Event Understanding owner
Authoritative enrichment owner
Canonical Identity owner
Generation owner
Verification owner
Publication Contract owner
PWA renderer
Push delivery
```

For each owner, specify:

- input contract;
- output contract;
- allowed decisions;
- forbidden decisions;
- failure/defer behavior;
- fallback/escalation owner;
- legacy paths to remove in Phase 4.

No provider search loop resumes merely because Phase 1 is complete. Provider selection remains blocked unless/until the architecture requires and a provider satisfies the frozen qualification contract.
