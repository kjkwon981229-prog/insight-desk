# PHASE 4 — OpenRouter Nemotron Event Understanding Candidate

Status: `NOT_QUALIFIED UNDER ACTIVE QUALIFICATION V2 / NO PRODUCTION WIRING`

Candidate provider: OpenRouter
Candidate model: `nvidia/nemotron-3-super-120b-a12b:free`

## Candidate boundary

This was a qualification-only Event Understanding candidate. It has never been exported through the production provider package surface and has never been wired into production.

The model identity remains frozen to the explicit `:free` variant. The random `openrouter/free` router and the paid model variant are forbidden. The request requires structured-output support and does not allow cross-model fallback.

## Why qualification V2 replaced V1

The original bounded V1 protocol correctly required source-grounded structure, but its scorer also searched free-form semantic fields for exact Korean literals. Exact source provenance was already mechanically bound by `UnderstandingEvidenceRef` source ranges and SHA-256 digests, so that extra lexical-reproduction requirement mixed string reproduction into semantic understanding evaluation.

The provider-neutral audit therefore replaced only the qualification protocol, not the production semantic prompt/schema or any provider-specific settings. V2 keeps:

- the same four recoverable historical exact-source excerpt cases;
- the same semantic topic scopes;
- the same Event Understanding JSON schema;
- exact source-range evidence binding;
- PRIMARY / SUPPORTING / CONTEXT structure;
- DIRECT / INDIRECT_EFFECT / BACKGROUND / INCIDENTAL / UNRELATED / UNRESOLVED relations;
- entity preservation through actor/object/participants;
- distinct event decomposition;
- parent grouping requirements where applicable.

V2 removes only gold-literal comparison against free-form action/event-type/attribution/parent-hint wording. Source facts are scored through the exact evidence ranges selected by each event draft.

Offline protocol tests prove that semantic paraphrase can pass, missing structured entities fail, free-text wording cannot replace evidence, context cannot satisfy a primary/direct event, and one collapsed draft cannot satisfy two expected events.

## Historical V1 evidence

Valid configured V1 run `33057003750`, head `7b1230ea9ae5d0b5da3dc5725df55b2bb9fea1bf`:

- evaluated: 4
- passed: 1
- BOK rate: FAIL `required_structured_literal`
- BOK outlook: FAIL `provider_transport:invalid_output`
- K-POP: FAIL `provider_transport:invalid_output`
- KBO: PASS
- artifact `9640144162`
- digest `sha256:20a5a412407d5d1e80e4f14b1a23622872f3932cdf8f882debed6c0e85d90b61`

This evidence is retained as historical context and is not rewritten as a V2 result.

## Final V2 one-shot result

After qualification V2 was independently audited and its ordinary CI plus historical compatibility replay were GREEN, one explicit V2 requalification was permitted because OpenRouter was the only previous candidate whose V1 result included a scorer-level failure. Gemini and Mistral had failed before scoring with ContractError, while Groq 20B had transport failures, so they were not rerun.

Exact V2 push run `33069019702`, head `f6e379f0bb1ca8d092e2d69f905c223bbc0a5f6a`:

- infrastructure: SUCCESS
- historical-production-replay: SUCCESS
- qualification protocol: 2
- evaluated: 4
- passed: 0
- status: `NOT_QUALIFIED`

Per case:

- `run413-bok-kbs-rate-decision`: FAIL — `provider_or_contract_error:ContractError`
- `run413-bok-kmib-outlook-child`: FAIL — `provider_or_contract_error:ContractError`
- `run413-kpop-alphadriveone-actor-preserved`: FAIL — `provider_or_contract_error:ContractError`
- `run413-kbo-osen-same-game-source`: FAIL — `provider_transport:invalid_output`

Evidence artifact:

- artifact id: `9644987975`
- digest: `sha256:d01c86cb1c372faa678fb038bda4edc169dfd3ed05313d35b815d40ff3d32008`

The V2 result is final for this fixed provider/model contract. No prompt/schema/scope/gold/scorer tuning or retry is authorized.

## Frozen consequence

`OpenRouter + nvidia/nemotron-3-super-120b-a12b:free` remains `NOT_QUALIFIED`, now under the active provider-neutral qualification protocol V2.

The machine provider inventory remains `NO_ELIGIBLE_EXISTING_PROVIDER`, `selected_event_understanding_provider` remains null, and `production_wired` remains false.

The one-shot V2 workflow is removed after freezing the result. No production marker, fresh discovery, PWA build, deploy, or Push is authorized.

A future provider may be considered only as a new independent candidate satisfying the existing architecture constraints. It must use qualification V2 unchanged and exactly once. Existing generation, verification, identity, or temporal owners may not be silently repurposed.

Even a future `MINIMUM_COMPATIBILITY_PASS` does not itself authorize production wiring. The PHASE 4 migration gate must still remove the three legacy semantic bypasses and preserve source-range-bound Event Understanding output before production rewiring can open.
