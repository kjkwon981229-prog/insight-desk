# Cerebras Gemma 4 31B — Event Understanding V4 candidate

This branch prepares one qualification of exact model `gemma-4-31b` under the frozen active Event Understanding V4 contract.

## Eligibility checked before implementation

- Cerebras public model inventory currently lists exact ID `gemma-4-31b` as non-deprecated and production (`preview=false`).
- The same inventory advertises structured-output capability for this model.
- Cerebras structured-output documentation supports strict JSON Schema responses.
- The repository already has the `CEREBRAS_API_KEY` credential boundary from historical Cerebras qualification; no new secret is introduced.
- This is not a retry of historical Cerebras `zai-glm-4.7`; the exact model identifier is different.
- The model has no frozen production semantic-owner responsibility in Insight Desk.
- The qualification remains within the existing zero-cost/free-credit policy; no paid fallback is introduced by this branch.

## Qualification transport boundary

The candidate uses the Cerebras chat-completions endpoint:

`https://api.cerebras.ai/v1/chat/completions`

Request binding is frozen to:

- exact model `gemma-4-31b`
- strict `response_format.type = json_schema`
- unchanged active V4 schema passed to `response_format.json_schema.schema`
- `strict = true`
- `temperature = 0`
- `max_completion_tokens = 2048`
- generic HTTP transport `attempts = 1`

There is no output repair, provider fallback, model alias fallback, or hidden HTTP retry.

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no provider retry loop
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this candidate branch

The client is qualification-only and is not exported from `insight_desk.providers`.

## Execution gate

No live Cerebras call is permitted until the exact candidate head passes ordinary Infrastructure, historical production replay, and Phase 6 correctness/recall. Only then may one marker-gated one-shot V4 qualification run. The first valid result for exact route `gemma-4-31b` is final and must be frozen before any further provider work.
