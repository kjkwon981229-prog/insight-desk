# PHASE 4 — Event Understanding Provider Block

Status: `CANDIDATE_QUALIFICATION_BLOCKED / NO SELECTED PROVIDER`

## Current qualification inventory

- Groq GPT-OSS 20B (`openai/gpt-oss-20b`): historical protocol 1 `NOT_QUALIFIED`; generation responsibility remains separate.
- Gemini Flash Lite (`gemini-3.1-flash-lite`): historical protocol 1 `NOT_QUALIFIED`; verification-failover responsibility remains separate.
- OpenRouter Nemotron (`nvidia/nemotron-3-super-120b-a12b:free`): active protocol 3 `NOT_QUALIFIED`, 0/4; fixed result includes invalid structured output and an adapter evidence-contract failure.
- Cohere Command A+ (`command-a-plus-05-2026`): active protocol 3 `NOT_QUALIFIED`, 0/4; run `33104385499` reached the frozen adapter on all four cases and each ended with `adapter_contract:adapter_output_contract`. Artifact `9659910291`, digest `sha256:73594960aa92f046fef4e7ee151721b6d40ba09e064963f9d3f5ba619f567259`.
- Mistral Large 3 (`mistral-large-2512`): active protocol 3 `QUALIFICATION_BLOCKED_TRANSIENT`; run `33094503683` could not complete semantic qualification because all four cases ended in transient provider transport failure.
- Groq GPT-OSS 120B: `EXCLUDED`; temporal auxiliary responsibility remains frozen.
- Cloudflare Llama 3.3 70B: `EXCLUDED` from Event Understanding reassignment; primary verification responsibility remains frozen.
- Local mDeBERTa NLI: `EXCLUDED` from Event Understanding reassignment; secondary verification responsibility remains frozen.

The Mistral blocked state is intentionally distinct from `NOT_QUALIFIED`. It does not make Mistral eligible for selection, but it also does not claim semantic incompatibility when the provider returned no assessable result.

The Cohere result is definitive under the frozen active protocol. It is not a credential or transient-provider outcome, and the one-shot Cohere qualification lane is removed after the result is frozen. No prompt, schema, source fixture, gold, scorer, or acceptance rule is changed to obtain another attempt.

## Mechanical state

`config/event_understanding_provider_status_v2.json` declares:

```text
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
selected_event_understanding_provider = null
production_wired = false
```

The selector rejects all of the following:

- selecting a `NOT_QUALIFIED` provider;
- selecting an `EXCLUDED` provider;
- selecting a credential-blocked or transiently blocked provider;
- selecting any provider while inventory status is not `ELIGIBLE_CANDIDATE_AVAILABLE`;
- setting `production_wired=true` without a selected active-protocol qualified provider.

## Qualification lifecycle boundary

Operational inability to finish qualification is not semantic evidence. The active lifecycle keeps credential absence and transient/rate-limited provider transport separate from definitive incompatibility. Conversely, invalid output, adapter/contract failures, semantic scoring failures, or other definitive case failures remain `NOT_QUALIFIED` and cannot be converted into a blocked state to obtain another attempt.

No automatic provider retry is enabled. A blocked qualification may only be continued by an explicit, separately gated one-shot using the unchanged provider/model/prompt/schema/gold/scorer contract after the lifecycle implementation itself is GREEN.

Even a later `MINIMUM_COMPATIBILITY_PASS` does not authorize production wiring by itself. The PHASE 4 migration gate must still close its legacy semantic bypasses and preserve source-range-bound Event Understanding before production rewiring can open.

No production marker, fresh news canary, deploy, Push, or merge is authorized by this provider-state update.
