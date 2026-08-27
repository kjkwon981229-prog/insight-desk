# PHASE 4 — OpenRouter Nemotron Event Understanding Candidate

Status: `NOT_QUALIFIED UNDER ACTIVE QUALIFICATION V3 / NO PRODUCTION WIRING`

Candidate provider: OpenRouter  
Candidate model: `nvidia/nemotron-3-super-120b-a12b:free`

## Candidate boundary

This is a qualification-only Event Understanding candidate. It has never been exported through the production provider package surface and has never been wired into production.

The model identity remains frozen to the explicit `:free` variant. The random `openrouter/free` router and the paid model variant are forbidden. The request requires structured-output support and does not allow cross-model fallback.

## Protocol history

The historical V1 and V2 results remain immutable evidence. They are not promoted into the active protocol and cannot satisfy provider selection.

V2 removed free-form gold-literal scoring while preserving exact source-range evidence scoring. V3 does not change the semantic gold, topic scopes, acceptance threshold, provider policy, core contract, or structured-output schema. It creates a new qualification protocol because the corrected adapter/source contract now hands Event Understanding:

- source publisher, URL, and known publication time;
- unknown historical publication time as unknown rather than replay-clock proxy;
- explicit zero-based evidence start/end offsets validated against exact source bytes.

The active qualification fixture is `tests/fixtures/event_understanding_qualification_v3.json`. The core contract remains `event_understanding_v2` and the structured-output schema remains `event_understanding_schema_v2`.

## Historical V1 evidence

Valid configured V1 run `33057003750`, head `7b1230ea9ae5d0b5da3dc5725df55b2bb9fea1bf`:

- qualification protocol: 1
- evaluated: 4
- passed: 1
- artifact: `9640144162`
- digest: `sha256:20a5a412407d5d1e80e4f14b1a23622872f3932cdf8f882debed6c0e85d90b61`

## Historical V2 evidence

Exact V2 push run `33069019702`, head `f6e379f0bb1ca8d092e2d69f905c223bbc0a5f6a`:

- qualification protocol: 2
- evaluated: 4
- passed: 0
- status: `NOT_QUALIFIED`
- artifact: `9644987975`
- digest: `sha256:d01c86cb1c372faa678fb038bda4edc169dfd3ed05313d35b815d40ff3d32008`

The V1 and V2 records remain historical only. Neither can be reused as an active V3 qualification result.

## Failure observability prerequisite

Before the V3 provider call, qualification failure reporting was repaired and independently validated so that adapter contract failures expose only bounded stage codes. The allowed diagnostic form is stage-level, for example `adapter_contract:evidence_contract`; article text, date strings, raw exception text, and provider payloads are not written into the qualification report.

The observability GREEN commit is `9fe92517a29ba2b9963ae72f03e6c409adef9274`. Its exact-head Infrastructure CI and historical production replay both succeeded, and the corresponding Daily production workflow kept build, deploy, and push skipped.

## Final V3 one-shot result

Only after the corrected V3 contract and failure observability were GREEN was one bounded OpenRouter Nemotron V3 qualification allowed.

Exact push run `33093075809`, head `84ec074fda93d7fa1e4537e6bbfde26d5a58eb31`:

- infrastructure: SUCCESS
- historical-production-replay: SUCCESS
- qualification protocol: 3
- evaluated: 4
- passed: 0
- status: `NOT_QUALIFIED`

Per case:

- `run413-bok-kbs-rate-decision`: FAIL — `provider_transport:invalid_output`
- `run413-bok-kmib-outlook-child`: FAIL — `provider_transport:invalid_output`
- `run413-kpop-alphadriveone-actor-preserved`: FAIL — `provider_transport:invalid_output`
- `run413-kbo-osen-same-game-source`: FAIL — `adapter_contract:evidence_contract`

Evidence artifact:

- artifact id: `9655338800`
- digest: `sha256:0f06113d6ce5e5affcadde365474bbd12d4016f88ed7fa54a97d8a4e625834dc`

The bounded artifact contains stage-coded failures only. It does not contain article body text, date strings, raw exception messages, or provider payloads.

This V3 result is final for the fixed OpenRouter/model/contract combination. No prompt, schema, source contract, semantic scopes, scorer, gold, or candidate-specific retry is authorized from this result.

## Frozen consequence

`OpenRouter + nvidia/nemotron-3-super-120b-a12b:free` is `NOT_QUALIFIED` under the active qualification protocol V3.

The machine provider inventory remains `NO_ELIGIBLE_EXISTING_PROVIDER`, `selected_event_understanding_provider` remains null, and `production_wired` remains false. The one-shot V3 workflow is removed after freezing the result, so an ordinary push cannot silently re-run this candidate qualification.

No production marker, fresh discovery/live canary, PWA build, deploy, Push, or merge is authorized by this qualification result.

A future Event Understanding candidate, if considered, must be an independent provider/model contract that satisfies the frozen single-owner architecture and uses protocol V3 unchanged exactly once. Existing generation, verification, identity, or temporal owners may not be silently repurposed.

Even a future `MINIMUM_COMPATIBILITY_PASS` would not itself authorize production wiring. The PHASE 4 migration gate remains closed until the legacy semantic bypasses are removed and identity consumes source-range-bound CanonicalEvent drafts without raw-source reinterpretation.
