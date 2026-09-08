# Gemini 3.5 Flash-Lite — Event Understanding V4 qualification evidence

`gemini-3.5-flash-lite` was qualified exactly once under the active frozen V4 Event Understanding contract.

## Eligibility checked before implementation

- exact model ID: `gemini-3.5-flash-lite`
- stable / GA model
- Gemini Interactions API supported
- structured outputs supported
- free-tier input and output available
- repository operating-cost requirement remains KRW 0
- production Gemini verification-failover owner remains separately frozen to `gemini-3.1-flash-lite`
- no prior Event Understanding qualification record existed for this model

## Frozen qualification boundary

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no retry loop
- no production wiring, legacy-blocker removal, fresh canary, deploy, Push, or merge from this qualification

The candidate reused only the already-isolated Gemini qualification transport contract. It did not repurpose the production Gemini verification-failover owner.

## Pre-qualification gate

The qualification-only wiring passed the ordinary infrastructure suite and the historical production replay / Phase 6 correctness-recall gate before the one-shot provider call. A temporary legacy-lane name-prefix assertion collision was corrected as a test-only exact-match fix; the failed preflight did not invoke the provider.

## First and only result

```text
provider = gemini35_flash_lite
model = gemini-3.5-flash-lite
status = NOT_QUALIFIED
evaluated_cases = 4
passed_cases = 1
failure_classification = EVENT_DRAFT_CONTRACT
```

Case results:

```text
run413-bok-kbs-rate-decision        FAIL  adapter_contract:event_draft_contract
run413-bok-kmib-outlook-child      FAIL  adapter_contract:event_draft_contract
run413-kpop-alphadriveone-actor-preserved  PASS
run413-kbo-osen-same-game-source   FAIL  adapter_contract:event_draft_contract
```

This is definitive active-V4 non-qualification evidence, not a transport/transient/provider-availability block. No retry or model-specific contract tuning is permitted.

## Exact evidence binding

- qualification run: `33154997997`
- exact qualification head: `9aae9e36c1358fc3693118d99c2bd9da796f8a4a`
- report SHA-256: `73762b6e18f9d8c05c2ce7cf6575c2bff383907dacc6f02b78c8c6d160b44f0b`
- artifact ID: `9679252510`
- artifact ZIP SHA-256: `dbcf2e735404a3267f862dd90ebb1a9b5475e0c73994eb255bba2d247d43a6fc`

The uploaded artifact ZIP and contained qualification report were independently re-hashed and matched the Actions digests exactly.

## Consequence

`gemini-3.5-flash-lite` is not selectable under active V4. The machine inventory remains `CANDIDATE_QUALIFICATION_BLOCKED` because the previously frozen active-V4 Gemini 2.5 Pro provider-unavailable result is still present. The selected Event Understanding provider remains `null`, production remains unwired, and all three Phase 4 migration blockers remain active.

The consumed one-shot qualification lane has been removed. The next permitted provider action is qualification of one new eligible provider/model under the same frozen V4 contract; Gemini 3.5 Flash, Gemini 3.6 Flash, Gemini 2.5 Pro, and Gemini 3.5 Flash-Lite must not be retried or tuned.
