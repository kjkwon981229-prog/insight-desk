# Phase 12B — Provider Resilience Architecture

Status: DESIGN FROZEN FOR REGRESSION-FIRST IMPLEMENTATION
Date: 2026-08-23

## Objective

Prevent any single free provider, quota bucket, rate limit, or transient service failure from collapsing an otherwise valid briefing to zero cards. Provider availability must never be interpreted as content correctness.

This phase does not relax evidence, semantic, preservation, or publication correctness. It changes orchestration and availability handling only.

## Newly confirmed root causes

### RC-7 — Verification availability collapses into content acceptance

The current generated-claim gate requires Cloudflare primary plus local mDeBERTa secondary. When Cloudflare returns no entailment because its daily free quota is exhausted, otherwise valid candidates become INDETERMINATE and are dropped. A provider-capacity failure therefore has the same product outcome as unsupported content.

### RC-8 — HTTP 429 taxonomy collapse

The shared JSON transport currently maps every HTTP 429 to FREE_QUOTA_EXHAUSTED. This is incorrect across providers. Cloudflare can use 429 for exhausted daily free neurons, while Groq uses 429 for RPM/TPM/RPD/TPD rate limits. Their recovery horizons differ and must not share one failure state.

### RC-9 — Pull-request path filters amplify live-production consumption

GitHub evaluates pull_request path filters using the PR three-dot diff. Once a PR contains a production-critical path, later synchronize events can continue to satisfy that filter even when the latest development commit is unrelated. This caused repeated live production executions during Phase 12 development and consumed shared free-provider quota.

The production workflow is now guarded so PR live production requires an explicit `[production-preflight]` marker on the exact current head commit. Main push/schedule behavior remains unchanged.

### RC-10 — No provider circuit or role-level availability state

Production retries providers at item scope without a run-level provider state. Once a provider has returned a definitive daily-quota failure, later candidates can continue calling the same unavailable provider. There is no OPEN/CLOSED circuit, cooldown horizon, or role-level capacity verdict.

### RC-11 — Exact-source fallback is over-verified

The extractive fallback is deterministically copied from cited EvidenceSpan text and already passes preservation/provenance contracts, but Phase 7 still sends it through the same external semantic-verification path as generated prose. This makes a zero-generation, source-exact safety path dependent on external LLM availability.

## Resilience policy

"Three tools" means three usable execution paths for externally fallible critical roles, not three names sharing one quota bucket.

A deterministic pure-local stage does not need three competing implementations merely to satisfy a numeric rule. It needs independent validation and a safe fallback. External or quota-bound stages must not have one provider capable of reducing the entire feed to zero.

## Role inventory and target paths

### Discovery

1. NAVER Search API — existing primary for Korean news discovery.
2. Gemini search-grounded discovery — reserve path; query strings only, never article body as discovery input.
3. Topic-specific direct/official feeds or RSS/API adapters — reserve path where available.

GDELT is not selected as the Korean-news third path because its DOC API phased out native-language search support and is not an adequate Korean replacement for NAVER.

### Acquisition

1. Direct HTTP fetch + Trafilatura — existing primary.
2. Direct HTTP fetch + deterministic alternate extractor such as jusText — local extraction fallback.
3. Playwright-rendered HTML + deterministic extractor — browser fallback.
4. Original/alternate article URL pair — source-route fallback, while retaining one-source-one-card identity.

### Fact extraction

1. Kiwi deterministic fact extraction — existing primary.
2. Sentence-local exact-source deterministic fallback — must preserve offsets and may only emit facts representable by source text.
3. Optional structured free-provider extraction — only when configured, with exact source offsets mandatory and FactDraft validation authoritative.

No LLM extraction may invent facts or bypass exact EvidenceSpan validation.

### Generation

1. Groq GPT-OSS 20B — existing primary.
2. Gemini Flash-Lite free tier — alternate independent provider when configured and healthy.
3. Deterministic exact-source fallback — final zero-generation path.

No paid route is allowed. Provider failure is not preservation failure.

### Verification of generated prose

Primary verifier slot:
1. Cloudflare Workers AI — existing primary.
2. Gemini Flash-Lite — independent primary failover.

Local secondary verifier slot:
3. mDeBERTa XNLI — existing local secondary.
4. multilingual MiniLM MNLI/XNLI — local secondary failover.

The frozen two-slot semantic rule remains: one available primary plus one available local secondary must support the claim. Phase 12B does not introduce majority voting and does not lower the support threshold.

A provider being unavailable is never an explicit content rejection.

### Verification of exact-source fallback

Exact-source fallback is not generated prose. Publication support is established by deterministic proof:

- output characters are an exact substring/excerpt of cited EvidenceSpan text;
- cited EvidenceSpan offsets validate against the immutable RawArticle;
- preservation report is accepted;
- no text outside the cited event evidence appears in the card.

External LLM availability is not a publication dependency for this render mode. Optional semantic verifiers may audit it, but may not turn provider unavailability into content rejection.

### Rendering / artifact publication

Rendering remains one deterministic implementation. Redundancy is provided by independent validators and exact artifact hashes rather than multiple renderers:

1. renderer contract validation;
2. feed-quality validator;
3. independent exact-artifact revalidation/render QA.

Adding multiple render engines would increase divergence rather than availability.

## Provider state model

Provider state and content verdict are separate dimensions.

Required provider availability states:

- HEALTHY
- TRANSIENT_FAILURE
- RATE_LIMITED
- DAILY_QUOTA_EXHAUSTED
- CONFIG_MISSING
- INVALID_OUTPUT
- OPEN_CIRCUIT

Required rules:

1. HTTP 429 is initially RATE_LIMITED unless a provider adapter can positively identify a daily/account quota exhaustion condition.
2. Cloudflare internal code 3036 / daily-free-allocation evidence maps to DAILY_QUOTA_EXHAUSTED and opens the circuit for the rest of the run.
3. Groq 429 remains RATE_LIMITED and obeys Retry-After / rate-limit reset information where available; it must not be mislabeled as daily quota exhaustion.
4. A definitive DAILY_QUOTA_EXHAUSTED state prevents further calls to that provider in the same run.
5. A provider circuit applies to provider availability only; it never mutates a claim to REJECTED.
6. If a required verifier slot has no healthy route, the run/candidate records INSUFFICIENT_VERIFICATION_CAPACITY rather than CONTENT_REJECTED.

## Budget policy

- Development commits do not automatically run live production.
- Only an explicit exact-head production-preflight candidate consumes PR live quota.
- Main scheduled production remains once daily.
- Every external provider has a per-run call ceiling.
- Definitive quota exhaustion opens the circuit immediately; no repeated candidate-level calls.
- Rate-limit errors honor provider retry/reset information and have a bounded retry budget.
- No paid fallback can be entered automatically.

## Acceptance invariants for Phase 12B

1. PROVIDER_UNAVAILABLE != CONTENT_REJECTED.
2. One provider quota failure cannot by itself reduce an otherwise source-exact briefing to zero.
3. Exact-source fallback does not require an external LLM to prove that copied source text is sourced.
4. Generated prose retains two independent verification slots.
5. Primary verifier failover does not change semantic thresholds.
6. Local secondary verifier failover does not change semantic thresholds.
7. One definitive daily-quota response opens a run-level circuit and prevents repeated calls.
8. Generic 429 and daily-quota exhaustion are distinguishable.
9. PR development commits do not launch expensive production unless the exact head is explicitly marked `[production-preflight]`.
10. Canonical PR production checks out the exact PR head SHA, not an implicit merge ref.
11. No paid provider path exists.
12. No article body, generated headline/summary, or secrets are added to logs merely for provider routing.

## Current candidate evaluation

- Cloudflare: keep as generated-prose primary verifier, but quota state must be budgeted/circuit-broken. Multiple Cloudflare models do not count as independent paths because they share the account neuron allocation.
- Groq: keep as generation primary. Current free GPT-OSS 20B limits include RPM/TPM/RPD/TPD dimensions, so pacing must not treat RPM alone as sufficient.
- Gemini Developer API: selected as independent free-provider candidate. Stable Gemini 3.1 Flash-Lite supports structured outputs and has a Free Tier. Free-tier data handling must be considered; only evidence-bounded public article text may be sent, never secrets or private data.
- OpenRouter Free: reserve/emergency candidate only. Free accounts are limited to roughly 50 free-model requests/day and the service itself describes free models as unsuitable for production reliability.
- Cerebras: rejected as a permanent-free dependency because its no-cost access is a time/credit-bounded free trial rather than a renewing free tier.
- GitHub Models: rejected; the service was retired on 2026-07-30.
- multilingual MiniLM MNLI/XNLI: selected as local-secondary failover candidate, pending regression benchmark against the locked positive/negative verification corpus.

## Implementation order

1. Lock RC-7 through RC-11 in regressions.
2. Split RATE_LIMITED from DAILY_QUOTA_EXHAUSTED semantics.
3. Add provider circuit state and no-repeat-on-open behavior.
4. Make exact-source fallback deterministic-proof publication independent of external LLM availability.
5. Add local MiniLM secondary route and benchmark it.
6. Add Gemini adapter interfaces and mocked contract tests; activate live only when a zero-cost credential is configured.
7. Wire generation and verification failover without changing semantic thresholds.
8. Run full static CI.
9. Run bounded provider canaries, not full production.
10. Mark one exact head `[production-preflight]` and run exactly one canonical live production.
11. Resume Phase 12 Steps 8–11 on that one artifact.
