# Gemini 2.5 Flash — Event Understanding V4 candidate

This branch prepares exactly one qualification of `gemini-2.5-flash` under the active frozen V4 contract.

## Eligibility checked before implementation

- exact stable model ID: `gemini-2.5-flash`
- no shutdown date announced in the current Gemini deprecation table
- structured outputs supported
- Standard Free Tier input and output are free of charge
- official REST route used here: `v1beta/models/gemini-2.5-flash:generateContent`
- qualification client uses the current generateContent structured-output contract, not Interactions
- `GEMINI_API_KEY` is already the repository credential boundary; no new secret is introduced
- production Gemini verification-failover owner remains separately frozen to `gemini-3.1-flash-lite`
- no prior Event Understanding qualification record exists for this exact model

## Why this route differs from Gemini 2.5 Pro

The earlier `gemini-2.5-pro` V4 attempt was frozen as provider unavailable after the Interactions endpoint returned HTTP 404 for all four cases. That result is not reclassified or retried. The current official Gemini documentation explicitly supports structured output for `gemini-2.5-flash` through generateContent, so this candidate uses that documented endpoint rather than assuming Interactions availability.

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
