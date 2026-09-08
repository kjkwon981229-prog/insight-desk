# HF Qwen3.6 35B / DeepInfra — Event Understanding V4 candidate

This branch prepares one provider qualification of `Qwen/Qwen3.6-35B-A3B:deepinfra` under the active frozen V4 contract.

## Eligibility checked before implementation

- Hugging Face Router exact model/provider route: `Qwen/Qwen3.6-35B-A3B:deepinfra`
- Hugging Face current provider/model documentation exposes structured output support for this DeepInfra route
- Hugging Face routed inference uses the existing `HF_TOKEN` credential boundary; no new secret is introduced
- current Hugging Face Free accounts receive a small monthly inference credit and routed inference does not silently create an automatic paid fallback without purchased credit
- current DeepInfra model pricing is low enough that the four bounded historical qualification cases are intended to remain within the existing zero-cost credit envelope when credit remains
- the older `Qwen/Qwen3-235B-A22B-Instruct-2507:nscale` V3 result remains historical evidence and is not retried or reclassified
- no existing production semantic-owner responsibility is assigned to this exact model/provider route

## Qualification transport boundary

The candidate uses Hugging Face Router's OpenAI-compatible chat-completions endpoint:

`https://router.huggingface.co/v1/chat/completions`

The request is frozen to:

- exact model/provider suffix `Qwen/Qwen3.6-35B-A3B:deepinfra`
- strict `response_format.type = json_schema`
- the unchanged active V4 schema passed verbatim to `response_format.json_schema.schema`
- `temperature = 0`
- `max_tokens = 2048`
- HTTP transport `attempts = 1`

There is no output repair, semantic fallback, provider fallback, model alias fallback, or hidden HTTP retry.

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

No live provider call is permitted until this branch's ordinary Infrastructure job, historical production replay, and Phase 6 correctness/recall gate are all GREEN on the exact candidate head. After those gates pass, exactly one one-shot V4 qualification may be triggered. The first valid result is final for this exact model/provider route and must be frozen before any further provider work.

Preflight head `c7627ce61dab71bfa0a9dc4a3a1bae0dfc0188ea` passed Infrastructure, historical production replay, and Phase 6 correctness/recall in run `33166053391`; the provider qualification job was SKIPPED because that commit carried no qualification marker.

## Frozen first valid result

The one permitted V4 qualification ran at exact head `3d716e45f8031b48fbc47c6a6110b5d580809252` in Actions run `33166122207`.

Result:

```text
status = NOT_QUALIFIED
evaluated_cases = 4
passed_cases = 0
failure_classification = MIXED_INVALID_OUTPUT_AND_TRANSIENT_FAILURE
```

Case failures:

- `run413-bok-kbs-rate-decision` -> `provider_transport:invalid_output`
- `run413-bok-kmib-outlook-child` -> `provider_transport:transient_provider`
- `run413-kpop-alphadriveone-actor-preserved` -> `provider_transport:invalid_output`
- `run413-kbo-osen-same-game-source` -> `provider_transport:transient_provider`

Because two cases contain definitive `invalid_output` failures, the mixed result is not eligible for `QUALIFICATION_BLOCKED_TRANSIENT`; it remains definitive `NOT_QUALIFIED`. The exact model/provider route must not be retried or candidate-specifically tuned.

Evidence binding:

- qualification run: `33166122207`
- exact qualification head: `3d716e45f8031b48fbc47c6a6110b5d580809252`
- artifact ID: `9683792273`
- artifact ZIP SHA-256: `fa52047919a441da4ad819ad39b257df5e58ef7721c5c0055c545f8e3addd81f`
- report SHA-256: `e2807cc45d6a2e45e653ced1831275b7363981b2d3b9ba90eb99ab208d025017`

The uploaded ZIP and contained report were independently re-hashed and matched the Actions evidence exactly. The consumed one-shot CI lane was removed immediately after the first result.

Machine state remains unselected and production-unwired. Existing active V4 provider-unavailable records still keep provider inventory at `CANDIDATE_QUALIFICATION_BLOCKED`. No migration blocker, production wiring, fresh canary, deploy, Push, or merge was touched.
