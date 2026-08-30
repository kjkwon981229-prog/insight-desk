# Cerebras Gemma 4 31B — Event Understanding V4 candidate

This branch records the single frozen qualification of exact model `gemma-4-31b` under the active Event Understanding V4 contract.

## Eligibility checked before implementation

- Cerebras public model inventory listed exact ID `gemma-4-31b` as non-deprecated and production (`preview=false`).
- The same inventory advertised structured-output capability for this model.
- Cerebras structured-output documentation supports strict JSON Schema responses.
- The repository reused the existing `CEREBRAS_API_KEY` credential boundary; no new secret was introduced.
- This was not a retry of historical Cerebras `zai-glm-4.7`; the exact model identifier is different.
- The model has no frozen production semantic-owner responsibility in Insight Desk.
- No paid fallback was introduced.

## Qualification transport boundary

The candidate used the Cerebras chat-completions endpoint:

`https://api.cerebras.ai/v1/chat/completions`

Request binding was frozen to:

- exact model `gemma-4-31b`
- strict `response_format.type = json_schema`
- unchanged active V4 schema passed to `response_format.json_schema.schema`
- `strict = true`
- `temperature = 0`
- `max_completion_tokens = 2048`
- generic HTTP transport `attempts = 1`

There was no output repair, provider fallback, model alias fallback, or hidden HTTP retry.

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no provider retry loop
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this candidate branch

The client remains qualification-only and is not exported from `insight_desk.providers`.

## Preflight evidence

Exact lane-install head `1737cd489dfa6bf87d40e4d71c153246e19c0c8d` passed Infrastructure, historical production replay, and Phase 6 in run `33168345153`; the provider job was SKIPPED because that commit carried no qualification marker.

Before lane installation, exact candidate head `64d9deeb3f38156265d4e5666bbc81aa302178a9` passed run `33168255731` with:

- Python: `1201 tests / 23 skipped / 0 failed`
- benchmark: `85 / 7 / 16 / 15 / 44`
- Push Worker: `20/20`
- npm audit: `0 vulnerabilities`
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS

## Frozen one-shot result

The one permitted qualification ran in Actions run `33168432708` on exact qualification head:

`23b4a8ad72d78dd61f6d8cfec2a9f9555ad8be48`

Result:

- provider: `cerebras_gemma4_31b`
- model: `gemma-4-31b`
- raw V4 status: `NOT_QUALIFIED`
- evaluated: `4`
- passed: `0`
- evidence classification: `ZERO_COST_ACCESS_UNAVAILABLE`

All four frozen cases returned the same bounded transport evidence:

`provider_transport:invalid_output + http_status:402`

This does **not** establish a semantic failure or semantic pass for Gemma 4 31B. The exact credential/path available to this project could not execute the bounded qualification under the project’s zero-cost policy. The active provider-status schema and validator were not changed to invent a 402-specific machine status after the result; the raw runner result remains `NOT_QUALIFIED` and the explanatory classification is evidence metadata only.

This exact provider/model route must not be retried or tuned under the current qualification policy.

Frozen artifact evidence:

- artifact ID: `9684571773`
- artifact ZIP SHA-256: `ab7e560d7370819fd9ff2ba0387b071bfa9158682342b7db474b61c145a88979`
- report SHA-256: `8fdd84a04d8061c999e58d3019d1ec54c5c2657875bd9b9f7ddd979d6ae2e434`
- artifact ZIP and report were independently re-hashed and matched the Actions evidence exactly
- the consumed marker-gated one-shot CI lane was removed immediately after the result

## Machine state after freeze

The new definitive non-pass does not create a selectable provider and does not erase the already-frozen active V4 provider-unavailable evidence. Therefore the existing machine state remains:

- `provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED`
- `qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION`
- `selected_event_understanding_provider = null`
- `production_wired = false`

The three production migration blockers remain active. No production wiring, migration contract, detector, schema, semantic gold, scorer, source fixture, deploy path, Push path, or fresh-live path was changed.

## Next permitted action

Qualify exactly one **new** eligible Event Understanding provider/model route under the same frozen V4 contract. Before its single call, independently verify current exact model availability, structured-output/API automation support, an actual zero-cost route sufficient for the four bounded cases, and absence of semantic-owner conflict. No frozen route may be retried.
