# Phase 4 — Mistral Medium 3.5 Event Understanding V5 Evidence

Status: NOT_QUALIFIED — FROZEN — NO RETRY

## Exact route

- provider: Mistral AI
- qualification provider id: `mistral_medium35`
- exact model id: `mistral-medium-3-5`
- endpoint: `/v1/chat/completions`
- credential: existing `MISTRAL_API_KEY`
- production wiring: none
- qualification protocol: V5
- acceptance requirement: 4/4 only

This route is distinct from historical frozen `mistral-large-2512`. Neither route is eligible for a
rerun after its recorded qualification result.

## Provider prerequisites frozen before execution

Mistral's official documentation checked on 2026-08-28 identified Mistral Medium 3.5 as model
`mistral-medium-3-5`, GA v26.04, 256k context, with Structured Outputs and Chat Completions on
`/v1/chat/completions`.

Official references:

- `https://docs.mistral.ai/models/mistral-medium-3-5-26-04`
- `https://docs.mistral.ai/studio/conversations/structured-output`
- `https://docs.mistral.ai/api`

Mistral documentation also states that API access is enabled in Free mode by default without a
credit card, subject to usage/rate limits, and that Free mode uses included monthly usage. No paid
fallback or pay-as-you-go activation was added by this project.

Official references:

- `https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key`
- `https://docs.mistral.ai/admin/billing-usage/usage-limits`
- `https://docs.mistral.ai/admin/identity-access/api-keys`

Historical Actions evidence had already shown `MISTRAL_API_KEY` configured for the repository.

## Frozen V5 contract

The candidate used the canonical V5 contract without candidate-specific semantic tuning:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The four historical exact-source cases, source handoff, semantic gold, scorer, distinct event-draft
matching, deterministic exact-text evidence binding, deterministic output invariants, and 4/4
acceptance threshold were unchanged.

## Qualification-only implementation boundary

- `insight_desk/providers/mistral_medium35.py`
- `scripts/qualify_mistral_medium35_v5.py`
- `tests/test_mistral_medium35_v5_event_understanding_provider.py`
- this evidence document

The historical `insight_desk/providers/mistral.py` was not changed. The new client is not exported,
not selected, and not production-wired.

## Preflight evidence

Candidate head `40e7db524889ab14fe588accae9244775fa00886`, run `33180165827`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- Python: `1220 tests / 23 skipped / 0 failed`
- benchmark: `85 / 7 / 16 / 15 / 44`
- Push Worker: `20/20`
- npm audit: `0 vulnerabilities`
- provider calls: zero

Temporary-lane staging head `0f30a262e5d195c937094cd36364573119baf21a`, run `33180324677`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-mistral-medium35`: SKIPPED
- provider calls: zero

## Frozen one-shot result

Trigger head:

`3023001921a3b87c196d91bcf3dffb94dccaba46`

GitHub Actions run:

`33180474834`

Qualification job:

`98880355343`

Result:

- status: `NOT_QUALIFIED`
- provider: `mistral_medium35`
- model: `mistral-medium-3-5`
- protocol: `5`
- core contract: `event_understanding_v2`
- structured-output schema: `event_understanding_schema_v4`
- evaluated: `4`
- passed: `3`
- source mode: `historical_exact_source_excerpt_only`
- full production correctness claimed: `false`

Case results:

1. `run413-bok-kbs-rate-decision` — PASS
2. `run413-bok-kmib-outlook-child` — PASS
3. `run413-kpop-alphadriveone-actor-preserved` — PASS
4. `run413-kbo-osen-same-game-source` — FAIL: `expected_event_match`

This is a scorer-level semantic event-match failure. The structured transport, JSON-schema output,
V5 deterministic adapter contract, and exact-evidence binding completed far enough for the scorer to
emit `expected_event_match`; the result is not reclassified as a provider transport or adapter
contract failure.

Evidence artifact:

- artifact ID: `9689501036`
- artifact ZIP SHA-256: `3f0af22349d62b36bc44ce4bf59471d3a635928e4b3f9bc3873183017640707c`
- report SHA-256: `ccd0f3685dbac6b863cf98276b3b44ec38eae8113b76627d05c3d52e251d3211`

The artifact ZIP and internal report were independently re-hashed after download and matched the
Actions digest/report bytes. The report JSON independently reproduced the same 3/4 result and the
single KBO `expected_event_match` failure.

## Consumed lane

The one-shot qualification lane was removed immediately after evidence capture. `.github/workflows/ci.yml`
was restored to its ordinary workflow blob `72da8a9a2f8996ccdfb1af906c575911b25c28b0`.

`mistral-medium-3-5` is now a frozen failed V5 route. Do not retry it and do not tune the V5 prompt,
schema, source fixture, gold, scorer, or acceptance threshold in response to this result.

## Machine and migration consequence

This 3/4 result does not create an eligible provider. Machine state remains:

```text
active_qualification_protocol = 5
structured_output_schema = event_understanding_schema_v4
provider_inventory_status = NO_ELIGIBLE_EXISTING_PROVIDER
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
selected_event_understanding_provider = null
production_wired = false
```

The three migration blockers remain active. No production Event Understanding wiring, fresh canary,
deploy, Push, or merge is authorized by this result.
