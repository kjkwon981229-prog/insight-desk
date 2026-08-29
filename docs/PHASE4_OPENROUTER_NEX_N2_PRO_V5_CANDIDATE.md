# Phase 4 — OpenRouter Nex-N2-Pro Event Understanding V5 Candidate

Status: FROZEN — QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE

## Exact candidate route

- provider: OpenRouter
- qualification provider id: `openrouter_nexn2pro`
- exact model id: `nex-agi/nex-n2-pro:free`
- endpoint: `https://openrouter.ai/api/v1/chat/completions`
- credential: existing `OPENROUTER_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

Repository search found no pre-existing Nex-N2-Pro route before this candidate branch. This exact
model is distinct from every frozen OpenRouter Event Understanding route, including Nemotron 3 Super,
GLM 5.2, GPT-5.4 Mini, Qwen3 235B, and Dots3-Note Preview. No frozen exact route was retried or
reclassified.

## Provider eligibility evidence before the call

OpenRouter pages checked on 2026-08-29 identified `nex-agi/nex-n2-pro:free` as:

- a 397B-parameter sparse MoE with 17B active parameters;
- built by Nex AGI on a Qwen3.5 architecture with its own agentic post-training;
- reasoning-capable;
- supporting function calling and structured outputs;
- 262,144-token context;
- released 2026-06-08;
- explicitly free at $0 input/output on the free route.

OpenRouter also exposed structured-output telemetry and provider listings for the route at candidate
selection time. That evidence justified exactly one bounded qualification attempt; it does not
supersede the later exact API result.

Public references checked on 2026-08-29:

- `https://openrouter.ai/nex-agi/nex-n2-pro:free`
- `https://openrouter.ai/nex-agi/nex-n2-pro:free/providers`
- `https://openrouter.ai/nex-agi/nex-n2-pro:free/performance`

## Transport and structured-output boundary

The qualification-only client fixed the exact free model slug and used:

```text
POST https://openrouter.ai/api/v1/chat/completions
model = nex-agi/nex-n2-pro:free
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

`provider.require_parameters = true` prevented routing to a provider endpoint that could not accept
the requested structured-output parameters. The HTTP transport was constructed with `attempts=1`;
the one-shot execution could not hide automatic HTTP retries. No random free router was used.

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

- `insight_desk/providers/openrouter_nexn2pro.py`
- `scripts/qualify_openrouter_nexn2pro_v5.py`
- `tests/test_openrouter_nexn2pro_v5_event_understanding_provider.py`
- `tests/test_openrouter_nexn2pro_v5_qualification_freeze.py`
- this document

The candidate is not exported from `insight_desk.providers`, is not added to production selection,
and is not production-wired. The wrapper scope-registers it only inside the V5 qualification runner
and restores canonical runner state on exit.

## Preflight and staged one-shot gate

Qualification-only preflight head `83463473a1b9ee434aab0ae9e335a2f4ee4adcc4`, run `33232701196`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- Python: 1263 tests / 23 skipped / 0 failed
- benchmark: 85 / 7 / 16 / 15 / 44
- Push Worker: 20/20
- npm audit: 0 vulnerabilities
- provider calls: 0

Temporary-lane staging head `3cea0a5098c9407e77b5b8db3e0e0e5e78a3cfa1`, run `33232948886`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-openrouter-nex-n2-pro`: SKIPPED
- provider calls: 0

The single authorized trigger head was:

`e52138287f9a98d83e8ddf2ca0e34a427f1c1c40`

Run `33233007435`, job `99049074789` executed the route once after both ordinary dependencies were
again SUCCESS.

## First and only provider result

The canonical V5 runner returned:

```text
status = QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE
provider = openrouter_nexn2pro
model = nex-agi/nex-n2-pro:free
qualification_protocol = 5
evaluated_cases = 4
passed_cases = 0
```

All four cases failed with exactly:

```text
provider_transport:invalid_output
http_status:404
```

No case reached semantic scoring. The exact route is therefore not a semantic 0/4 result; it is an
active-protocol provider/model availability block under the repository's mechanical status contract.
The public model-page evidence observed before the call does not override the exact API 404 evidence.

Frozen evidence:

- workflow run: `33233007435`
- qualification job: `99049074789`
- trigger head: `e52138287f9a98d83e8ddf2ca0e34a427f1c1c40`
- artifact ID: `9709072951`
- artifact ZIP SHA-256: `fa488a030134094d2e30ea0850cfeb269a9a49ff167625544b301019274dfa2c`
- report SHA-256: `6878028b25ec743f29701c94248906eb1aa7a006231e8c119c02dd5a42f79285`

The downloaded artifact ZIP was independently re-hashed and matched the Actions digest. The internal
report was independently re-hashed and re-read; it reproduced the same four HTTP 404 failures.

There is no retry, alternate provider routing for this exact model, max-token change, prompt/schema
change, source/gold/scorer change, or reclassification. The exact route is frozen.

## Registry consequence

Because the unavailable result is from the active V5 protocol, the mechanical provider-status
contract requires:

```text
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
```

The five earlier active V5 provider results remain definitive `NOT_QUALIFIED` records. Nex-N2-Pro is
an additional availability block, not a selectable provider and not evidence that the semantic
contract should be weakened.

The consumed one-shot lane was removed immediately after evidence capture and `.github/workflows/ci.yml`
was restored to the ordinary workflow blob.

## Freeze-head validation

Final candidate freeze head `76082b0f8f9fa252b8eb6e3eadfc6661b62d36c6`, run `33233454081`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- Python: 1265 tests / 23 skipped / 0 failed
- benchmark: 85 / 7 / 16 / 15 / 44
- Push Worker: 20/20
- npm audit: 0 vulnerabilities

The first freeze-head CI attempt exposed five stale historical V5 freeze assertions that still pinned
the former global inventory state `NO_ELIGIBLE_EXISTING_PROVIDER`. They did not indicate provider or
production regressions. Those assertions were updated to the mechanically required current global
state `CANDIDATE_QUALIFICATION_BLOCKED`; each historical provider's own frozen evidence remained
unchanged. The final freeze head above is GREEN.

## Production and merge gates

The three migration blockers remain active and `production_rewire_allowed = false`. No production
Event Understanding wiring, fresh-live canary, deploy, Push, or merge is authorized. PR #84 remains
OPEN and UNMERGED until a V5 provider reaches 4/4 and all downstream migration/publication acceptance
gates are separately proven.
