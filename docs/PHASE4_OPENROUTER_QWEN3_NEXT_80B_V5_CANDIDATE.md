# Phase 4 — OpenRouter Qwen3-Next 80B Event Understanding V5 Candidate

Status: FROZEN — QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_qwen3next80b`
- exact model id: `qwen/qwen3-next-80b-a3b-instruct:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

The exact model is distinct from frozen Qwen routes including OpenRouter Qwen3 235B A22B 2507 and
Hugging Face/DeepInfra Qwen3.6 35B A3B. It is the Qwen3-Next 80B A3B Instruct model, not a rerun of a
frozen exact provider/model pair.

## Public provider evidence before the call

OpenRouter pages checked on 2026-08-29 identified `qwen/qwen3-next-80b-a3b-instruct:free` as:

- free, with zero prompt/completion token pricing on the free route;
- 262,144-token context;
- an instruction-tuned Qwen3-Next 80B A3B model;
- served by a free endpoint whose supported parameters included `Response Format`;
- recent endpoint uptime shown as 100%;
- structured-output error telemetry available for the endpoint.

Those public pages justified one bounded attempt. They do not override the exact API qualification
result below.

Public references checked on 2026-08-29:

- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/pricing`
- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/api`
- `https://openrouter.ai/qwen/qwen3-next-80b-a3b-instruct:free/performance`

## Transport and structured-output boundary

The qualification-only client fixed the exact free model slug and used:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = qwen/qwen3-next-80b-a3b-instruct:free
response_format = {
  type: json_schema,
  json_schema: {
    name: <schema name>,
    strict: true,
    schema: <frozen V5 schema>
  }
}
provider.require_parameters = true
```

`provider.require_parameters = true` prevented routing to an endpoint that could not accept the
requested structured-output parameters. The HTTP transport used `attempts=1`; no hidden HTTP retry was
allowed. No random free router was used.

No candidate-specific source, semantic prompt, gold, scorer, threshold, fixture, token-budget tuning,
or V5 schema change was introduced.

## Frozen V5 contract

The candidate received the canonical V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The same four historical exact-source cases, source metadata, semantic gold, scorer, distinct event
draft matching, exact-text evidence binding, deterministic invariants, and 4/4 acceptance applied.

## Isolation boundary

Qualification-only files:

- `insight_desk/providers/openrouter_qwen3next80b.py`
- `scripts/qualify_openrouter_qwen3next80b_v5.py`
- `tests/test_openrouter_qwen3next80b_v5_event_understanding_provider.py`
- `tests/test_openrouter_qwen3next80b_v5_qualification_freeze.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## Preflight and staged one-shot gate

Qualification-only preflight head `0ef0d0c3204a12299438ba371bd0fb2bb370a436`, run `33233784216`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- provider calls: 0

Temporary-lane staging head `ec35097e51ce761e1fae97d33c7d17940673f43d`, run `33233835884`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-qwen3-next-80b`: SKIPPED
- provider calls: 0

## Single qualification result

Single trigger head:

`ca056f6a7ccd8babc3d106ade393539595af2fc1`

Qualification run:

`33233896431`

Qualification job:

`99051453111`

Ordinary dependencies on the same trigger SHA completed successfully before the provider job:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS

The qualification itself executed once and produced this exact result:

```text
status = QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE
evaluated_cases = 4
passed_cases = 0
```

Every case failed identically:

```text
provider_transport:invalid_output
http_status:404
```

Affected cases:

1. `run413-bok-kbs-rate-decision`
2. `run413-bok-kmib-outlook-child`
3. `run413-kpop-alphadriveone-actor-preserved`
4. `run413-kbo-osen-same-game-source`

No case reached semantic scoring. Therefore this result is not a semantic 0/4 and must not be used to
claim that Qwen3-Next failed the Event Understanding semantics. It establishes that the exact
`qwen/qwen3-next-80b-a3b-instruct:free` API route was unavailable to the project qualification call at
the exact one-shot execution boundary.

The exact route is frozen. There is no retry, alternate routing, max-token change, prompt/schema/source/
gold/scorer change, or reclassification from this result.

## Artifact evidence

Artifact ID:

`9709329603`

GitHub Actions artifact ZIP digest:

`sha256:df1b83063608936a59a5b4daed10ada080af17d74111186c85997831a38efc32`

The downloaded ZIP was independently SHA-256 re-hashed and matched the Actions digest exactly.

The ZIP contained exactly one report:

`event-understanding-qualification.json`

Independent report SHA-256:

`sha256:1cc3d2c2f09c2e383d4a78bcd88a3c59d8d4c7b7f77760ea355d1beac638475a`

The report JSON was independently re-read and confirmed the same provider/model, V5 protocol, 4
cases, 0 passes, and four identical `invalid_output + HTTP 404` failures.

## One-shot lane removal

The consumed temporary candidate lane was removed immediately after evidence capture. Final ordinary
`.github/workflows/ci.yml` is restored to blob:

`72da8a9a2f8996ccdfb1af906c575911b25c28b0`

The freeze test explicitly prevents the candidate job, trigger marker, qualification script reference,
and artifact-lane name from remaining in the ordinary workflow.

## Current machine-state consequence

The active V5 inventory was already `CANDIDATE_QUALIFICATION_BLOCKED` because Nex-N2-Pro is also an
active provider-unavailable record. Adding this Qwen3-Next result therefore does not change the
machine-level state transition:

```text
active_qualification_protocol = 5
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
```

No provider is selectable.

## Production and merge gates

No migration blocker is removed. No production Event Understanding owner is wired. No bounded
production smoke, source-backed fresh replay, fresh canonical canary, PWA/Push acceptance, or merge is
authorized by this result.

Only a genuinely new active V5 provider/model with exact 4/4 minimum compatibility may open provider
selection and migration closure. PR #84 remains OPEN and UNMERGED.
