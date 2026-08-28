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
- no prior valid Event Understanding qualification record exists for this exact model

## Why this route differs from Gemini 2.5 Pro

The earlier `gemini-2.5-pro` V4 attempt was frozen as provider unavailable after the Interactions endpoint returned HTTP 404 for all four cases. That result is not reclassified or retried. Gemini 2.5 Flash uses the documented generateContent route.

## Harness correction before valid qualification

Run `33160317727` reached the generateContent endpoint but every request returned HTTP 400 before model output. The qualification client had incorrectly nested the Interactions-style `responseFormat` object inside `generationConfig`. Current generateContent REST documentation requires `responseMimeType` plus `responseJsonSchema` for this JSON-Schema path. Therefore that run is harness RED evidence, not provider qualification evidence, and must not be entered in the provider registry as `NOT_QUALIFIED`.

The corrected client is locked to:

- `generationConfig.responseMimeType = application/json`
- `generationConfig.responseJsonSchema = <frozen V4 schema>`
- no `generationConfig.responseFormat`
- HTTP transport attempts = 1

Corrected harness head `50e599b7907086e99ee49e4323888bd2de56b5f1` passed the ordinary Infrastructure suite, historical production replay, and Phase 6 correctness/recall gate in run `33160548020`. The qualification job was skipped on that preflight because the commit carried no qualification marker.

The first valid provider result after those gates is final; no semantic retry or candidate-specific tuning is permitted.

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no provider retry loop; the qualification client sets HTTP transport attempts to 1
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this candidate branch

The candidate client is qualification-only and is not exported from `insight_desk.providers`.
