# Gemini 2.5 Flash — Event Understanding V4 candidate

This branch prepares one valid provider qualification of `gemini-2.5-flash` under the active frozen V4 contract.

## Eligibility checked before implementation

- exact stable model ID: `gemini-2.5-flash`
- no shutdown date announced in the current Gemini deprecation table
- structured outputs supported
- Standard Free Tier input and output are free of charge
- official REST route used here: `v1beta/models/gemini-2.5-flash:generateContent`
- `GEMINI_API_KEY` is already the repository credential boundary; no new secret is introduced
- production Gemini verification-failover owner remains separately frozen to `gemini-3.1-flash-lite`
- no prior valid Event Understanding qualification record existed for this exact model before this branch

## Why this route differs from Gemini 2.5 Pro

The earlier `gemini-2.5-pro` V4 attempt was frozen as provider unavailable after the Interactions endpoint returned HTTP 404 for all four cases. That result is not reclassified or retried. Gemini 2.5 Flash uses the documented generateContent route.

## Harness correction before valid qualification

Run `33160317727` reached the generateContent endpoint but every request returned HTTP 400 before model output. The qualification client had incorrectly nested the Interactions-style `responseFormat` object inside `generationConfig`. Current generateContent REST documentation requires `responseMimeType` plus `responseJsonSchema` for this JSON-Schema path. Therefore that run is harness RED evidence, not provider qualification evidence, and is not entered in the provider registry.

The corrected client is locked to:

- `generationConfig.responseMimeType = application/json`
- `generationConfig.responseJsonSchema = <frozen V4 schema>`
- no `generationConfig.responseFormat`
- HTTP transport attempts = 1

Corrected harness head `50e599b7907086e99ee49e4323888bd2de56b5f1` passed the ordinary Infrastructure suite, historical production replay, and Phase 6 correctness/recall gate in run `33160548020`. The qualification job was skipped on that preflight because the commit carried no qualification marker.

## Valid qualification result

The first valid provider qualification was run exactly once after the corrected harness gates passed.

- run: `33160640114`
- qualification head: `ddd824b9a5c5d491f1db331a3b05d84f83b2d87a`
- status: `QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE`
- evaluated cases: 4
- passed cases: 0
- all four cases: `provider_transport:invalid_output`, `http_status:404`
- failure classification: `PROVIDER_MODEL_UNAVAILABLE`
- artifact ID: `9681493475`
- artifact ZIP SHA-256: `41d62d4fccae04ff2d12ee4ccb633d2d54ff9b78134821b1668a112b427e02bf`
- report SHA-256: `163a6b75147d39da5cb046c0dac99d0c44ad8c78e04e214b3bd8e5a686c252a1`

The artifact ZIP and inner report were independently rehashed and matched the Actions evidence. This result means the exact model route was unavailable within the repository/API credential boundary used by qualification. It does not claim that the model is globally absent from Gemini's public catalog.

No valid qualification retry was performed. The consumed one-shot CI lane was removed after evidence capture.

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no provider retry loop; the qualification client sets HTTP transport attempts to 1
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this candidate branch

The candidate client remains qualification-only and is not exported from `insight_desk.providers`. The provider registry remains unselected and production wiring remains disabled.
