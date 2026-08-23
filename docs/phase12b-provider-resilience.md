# Phase 12B — Provider Resilience Architecture

Status: IMPLEMENTATION CANDIDATE — STATIC GATE PASSED BEFORE FINAL CLEANUP; CANONICAL LIVE ACCEPTANCE NOT YET RUN
Date: 2026-08-23

## Objective

Prevent a single free provider, quota bucket, rate limit, model-runtime failure, or optional credential from collapsing an otherwise source-valid briefing to zero cards. Provider availability is a separate dimension from content correctness.

Phase 12B does not authorize unverified generated prose, lower evidence standards, add paid routes, or weaken the two-slot semantic rule for generated text. When generated prose cannot be verified because infrastructure is unavailable, the system may only downgrade to deterministic exact-source text proved from cited immutable EvidenceSpan bytes.

## Root causes closed by this phase

### RC-7 — Verification availability collapsed into content acceptance

Previously, Cloudflare primary unavailability produced `entailed=None`, the aggregate verdict became `INDETERMINATE`, and otherwise usable candidates disappeared. Thirty provider-capacity failures could therefore look like thirty semantic failures and produce zero cards.

Current contract:

- explicit semantic rejection remains a content decision;
- provider/config/runtime unavailability remains an availability decision;
- generated prose with unavailable verification is never published as generated prose;
- it receives exactly one deterministic exact-source fallback;
- exact-source text is published only when literal-source proof and preservation contracts pass.

### RC-8 — Generic HTTP 429 taxonomy collapse

Generic HTTP 429 is `RATE_LIMITED` unless a provider adapter positively proves a stronger quota condition. Cloudflare code 3036 / daily-free-allocation evidence maps to `FREE_QUOTA_EXHAUSTED` and opens its run-local circuit. Groq 429 remains rate-limit semantics unless stronger evidence exists.

### RC-9 — PR path filters amplified live-production quota use

Pull-request path filters operate on the PR diff, so later development commits could repeatedly launch production after a production-critical path had entered the PR. PR live production now requires the exact current head commit to contain `[production-preflight]`. Ordinary development commits do not run the heavy PR build.

### RC-10 — No provider circuit or role-level availability state

Quota/rate/config/provider states are now tracked separately from semantic verdicts. Definitive dead routes are skipped for later claims in the same run instead of being called repeatedly.

### RC-11 — Exact-source fallback was over-dependent on external verification

Exact-source fallback contains no generated paraphrase. It is therefore validated by deterministic substring/provenance/preservation proof rather than external LLM availability. External verifier outage cannot veto source-exact text merely because the verifier is unavailable.

## Current executable role architecture

### Discovery

Ordered zero-cost routes:

1. NAVER Search API when both NAVER credentials are configured.
2. Bing News RSS.
3. GDELT DOC.

NAVER credentials are optional as a pair. Both absent means the independent free routes remain usable. A partial NAVER credential pair is treated as configuration corruption and fails fast.

All routes normalize into the same `ArticleCandidate` contract. Search snippets are never promoted to article bodies.

### Article acquisition

Ordered extraction routes, all under the same deterministic quality gate:

1. HTTP + Trafilatura.
2. HTTP + deterministic `<article>/<main>` extractor.
3. Playwright-rendered HTML + Trafilatura.
4. Playwright-rendered HTML + deterministic `<article>/<main>` extractor.

The alternate extractor does not lower the existing quality threshold. Failed extraction remains item-local `EXTRACTION_EMPTY`.

### Fact extraction

Ordered exact-source routes:

1. Kiwi deterministic morphology/source-offset extractor.
2. PeCab-backed conservative surface parser.
3. Last-resort exact-surface deterministic parser for simple declarative Korean clauses only.

The PeCab route was accepted only after a Python 3.12 runtime canary. It validates POS structure while preserving exact source offsets. The surface-only route rejects complex or ambiguous clauses instead of guessing attachment. The composite preserves the existing external extractor identity so stable fact/event IDs are not needlessly churned.

PeCab canary evidence:

- workflow run: `32643504979`
- job: `97204112956`
- artifact: `9494239918`
- verdict: `PECAB_SEMANTIC_FALLBACK_CANARY_ACCEPTED`

### Generation

Ordered zero-cost recovery:

1. Groq GPT-OSS 20B when configured and available.
2. Gemini Flash-Lite free route when configured and available.
3. deterministic exact-source fallback.

Groq configuration is optional. No provider route is allowed to bypass preservation checks. No paid route exists.

### Verification of generated prose

Logical primary slot:

1. Cloudflare Workers AI when configured/healthy.
2. Gemini Flash-Lite as an independent failover when configured/healthy.

Local secondary slot:

3. measured mDeBERTa XNLI.

Generated prose still requires the normal primary logical slot plus the independent local secondary slot to support it. A primary explicit `False` remains rejection; failover cannot turn it into support. A local-secondary failure does not authorize generated prose.

If either required slot is unavailable and the generated result is therefore `INDETERMINATE`, Phase 7 downgrades to deterministic exact-source text instead of publishing unverifiable prose or discarding the source-valid event solely because infrastructure is unavailable.

The mDeBERTa model/runtime is lazy-loaded. Runtime/model-load failure is returned item-locally as `local_model_error:*`, which can lead to exact-source downgrade rather than a run-level crash.

### Verification of exact-source fallback

Exact-source fallback is supported only when:

- visible text is a literal excerpt of cited EvidenceSpan text;
- EvidenceSpan offsets validate against the immutable RawArticle;
- generation preservation is accepted;
- the deterministic source-proof verifier supports both visible roles.

It cannot manufacture paraphrased support and does not depend on an external LLM.

### Rendering and publication

Rendering remains one deterministic implementation. Redundancy is validation rather than divergent rendering semantics:

1. Phase 8 renderer contract;
2. feed-quality validator;
3. exact artifact hash binding;
4. same-artifact human review and desktop/mobile render QA.

## Optional-provider control plane

Provider credentials no longer form a global precondition for production.

The workflow reports configured routes without exposing values. Pair-valued providers enforce consistency:

- NAVER: both ID and secret present, or both absent;
- Cloudflare: both account ID and API token present, or both absent.

Partial pairs fail with `PHASE12B_PARTIAL_PROVIDER_CONFIG`. Complete absence is allowed where an independent zero-cost fallback exists.

Current zero-cost routes reported by the workflow include NAVER, Bing RSS, GDELT, Groq, Cloudflare, Gemini, local NLI, and deterministic exact source.

## Rejected local NLI fallback candidates

Acceptance threshold for an additional local semantic verifier was frozen at:

- positive >= 9/10;
- high-risk negative = 10/10.

Measured outcomes:

- `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`: positive 9/10, high-risk negative 5/10 — REJECTED.
- `MoritzLaurer/xlm-v-base-mnli-xnli`: positive 10/10, high-risk negative 9/10 — REJECTED.
- `joeddav/xlm-roberta-large-xnli`: positive 10/10, high-risk negative 8/10 — REJECTED.
- measured primary `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: positive 10/10, high-risk negative 10/10 — retained.

The threshold was not weakened to force a redundant local model into production. Rejected candidate code and marker-only benchmark jobs are removed from the final candidate tree.

## Canary and static evidence

Before final experiment cleanup, exact head `db7ee25b0e3cef0b8c0455c73e361c7e58116662` passed Infrastructure CI run `32644797487` (#1444):

- benchmark integrity: `hard_scored=85 evidence_only=7 taxonomy=16 run96_positive=15 run96_tn=44`;
- Python unittest: 250 total, 21 skipped, 229 non-skipped passed;
- Push Worker: 14/14 passed;
- npm audit: 0 vulnerabilities.

Gemini's bounded positive/negative live canary passed during Phase 12B provider validation. The experimental canary job is not retained in the final CI tree after its contract was established.

The previous static PASS does not automatically apply after final cleanup commits. A new exact-head CI is required before a production-preflight candidate may be marked.

## Acceptance invariants

1. `PROVIDER_UNAVAILABLE != CONTENT_REJECTED`.
2. Unavailable verification never authorizes generated prose.
3. Provider unavailability alone cannot erase a source-valid event when deterministic exact-source publication remains possible.
4. Explicit semantic rejection remains explicit rejection of generated prose.
5. Exact-source fallback requires literal-source deterministic proof.
6. Generic 429 and proven daily quota exhaustion remain distinct.
7. Definitive dead provider routes are circuit-broken within the run.
8. Optional provider absence does not stop unrelated independent zero-cost routes.
9. Partial multi-secret configuration fails fast rather than silently changing routing.
10. PR development commits do not run heavy production without exact-head `[production-preflight]`.
11. One exact PR head produces at most one canonical live acceptance artifact.
12. No paid provider path exists.
13. Article bodies, generated headline/summary text, and secrets are not added to provider-routing logs.
14. Merge remains blocked until the canonical live artifact passes automated, human, and render QA.

## Remaining gates

1. Finish final-tree cleanup and documentation synchronization.
2. Pass a fresh exact-head full Infrastructure CI after that cleanup.
3. Freeze that clean code head.
4. Create one minimal exact-head `[production-preflight]` candidate commit without semantic redesign.
5. Run exactly one canonical PR live production.
6. Validate the exact produced artifact bytes, production audit, and feed-quality report.
7. Perform full visible-card human audit.
8. Perform desktop/mobile render QA on the same artifact.
9. Only then decide candidate acceptance and merge.
