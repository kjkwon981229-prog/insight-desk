# Gemini 2.5 Pro — Event Understanding V4 qualification evidence

`gemini-2.5-pro` was qualified exactly once under the active frozen V4 Event Understanding contract.

## Frozen contract

- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v3`
- qualification protocol: 4
- source mode: `historical_exact_source_excerpt_only`
- acceptance: all four frozen historical cases must pass
- no prompt/schema/source/gold/scorer tuning
- no retry loop
- no production wiring, fresh canary, deploy, Push, or merge from this qualification

## First and only result

```text
provider = gemini25_pro
model = gemini-2.5-pro
status = QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE
evaluated_cases = 4
passed_cases = 0
failure_classification = PROVIDER_MODEL_UNAVAILABLE
```

All four frozen cases returned the same bounded transport evidence:

```text
provider_transport:invalid_output
http_status:404
```

This is an operational provider/model-unavailable result, not semantic `NOT_QUALIFIED` evidence and not a selectable compatibility PASS. The configured Gemini credential was present in the Actions qualification job. No retry or model-specific contract tuning was performed.

## Exact evidence binding

- qualification run: `33152273374`
- exact qualification head: `b02d7abc72cdda5302c8c24256ac0013e65b3a23`
- report SHA-256: `7607598c7b96ab6c76fd45b066339f3939a3e397de6671d274f8fb132a59d639`
- artifact ID: `9678194163`
- artifact ZIP SHA-256: `29b1c06e25b229a27673ba56ee5f26c9f009214c72c66168e83c0171c7c397df`

The uploaded artifact ZIP and contained qualification report were independently re-hashed and matched the Actions digests exactly.

## Consequence

`gemini-2.5-pro` is not selectable under active V4. Provider inventory remains without an eligible Event Understanding owner, production remains unwired, and the three Phase 4 migration blockers must remain active.

The consumed one-shot qualification lane has been removed. The next permitted provider action is qualification of one new eligible provider/model under the same frozen V4 contract; Gemini 3.5 Flash, Gemini 3.6 Flash, and Gemini 2.5 Pro must not be retried or tuned.
