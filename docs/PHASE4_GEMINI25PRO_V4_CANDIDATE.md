# Gemini 2.5 Pro — Event Understanding V4 candidate

This branch prepares exactly one qualification of `gemini-2.5-pro` under the active frozen V4 contract.

The active frozen contract remains unchanged:

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no retry loop
- no production wiring, fresh canary, deploy, Push, or merge from this candidate branch
