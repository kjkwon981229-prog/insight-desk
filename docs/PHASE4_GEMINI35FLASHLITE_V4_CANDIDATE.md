# Gemini 3.5 Flash-Lite — Event Understanding V4 candidate

This branch prepares exactly one qualification of `gemini-3.5-flash-lite` under the active frozen V4 contract.

## Eligibility checked before implementation

- exact model ID: `gemini-3.5-flash-lite`
- stable / GA model
- Gemini Interactions API supported
- structured outputs supported
- free-tier input and output available
- repository operating-cost requirement remains KRW 0
- production Gemini verification-failover owner remains separately frozen to `gemini-3.1-flash-lite`
- no prior Event Understanding qualification record exists for this model

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no retry loop
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this candidate branch

The candidate reuses only the already-isolated Gemini qualification transport contract. It does not repurpose the production Gemini verification-failover owner.
