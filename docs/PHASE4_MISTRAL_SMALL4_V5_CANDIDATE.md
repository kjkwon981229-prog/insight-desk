# Phase 4 — Mistral Small 4 Event Understanding V5 Qualification Evidence

Status: NOT_QUALIFIED — FIRST RESULT FROZEN — NO RETRY

## Exact route

- provider: Mistral AI
- qualification provider id: `mistral_small4`
- exact model id: `mistral-small-2603`
- endpoint: `/v1/chat/completions`
- credential: existing `MISTRAL_API_KEY`
- production wiring: none
- qualification protocol: V5
- acceptance threshold: 4/4 only

This exact route is now consumed and frozen. Frozen Mistral routes `mistral-large-2512`,
`mistral-medium-3-5`, and `mistral-small-2603` must not be retried or provider-specifically tuned.

## Current provider evidence checked before implementation

Mistral's official documentation checked on 2026-08-29 identified Mistral Small 4 as:

- model id `mistral-small-2603`;
- GA, v26.03;
- a hybrid generalist combining instruct, reasoning, and coding behavior;
- 119B total parameters / 6.5B active parameters;
- 256k context;
- supporting Structured Outputs on `/v1/chat/completions` and `/v1/conversations`.

Official references checked on 2026-08-29:

- `https://docs.mistral.ai/models/mistral-small-4-26-03`
- `https://docs.mistral.ai/models`
- `https://docs.mistral.ai/studio/conversations/structured-output`

The bounded qualification was authorized only against already included zero-cost usage in the
existing Mistral Workspace. No paid fallback or pay-as-you-go activation was enabled.

## Frozen V5 contract

No candidate-specific semantic contract was changed. The candidate received the canonical V5
contract frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The exact same four historical source cases, semantic gold, scorer, distinct event-draft matching,
exact-text evidence binding, deterministic invariants, and 4/4 threshold were used.

## Preflight evidence

Qualification-only candidate head `bff31dab5ce718bb5fb02a9a5fe0c98fcefdbd36`, run `33229136120`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- Python: `1228 tests / 23 skipped / 0 failed`
- benchmark: `85 / 7 / 16 / 15 / 44`
- Push Worker: `20/20`
- npm audit: `0 vulnerabilities`
- provider calls: zero

Temporary-lane staging head `f17c63f373a98da4c33967431b1f95dc1d4395c8`, run `33229185187`:

- Infrastructure: SUCCESS
- historical production replay: SUCCESS
- Phase 6 correctness/recall: SUCCESS
- `semantic-v5-provider-candidate-mistral-small4`: SKIPPED
- provider calls: zero

## One-shot qualification result

Trigger head:

`02e023f4c55902c5a8d40e6d6a0930ab12ada9e9`

GitHub Actions run:

`33229239969`

Result:

- status: `NOT_QUALIFIED`
- evaluated cases: `4`
- passed cases: `1`
- only passing case: `run413-kpop-alphadriveone-actor-preserved`

Failed cases:

- `run413-bok-kbs-rate-decision`
  - `status`
  - `primary_direct_min`
  - `expected_event_match`
- `run413-bok-kmib-outlook-child`
  - `adapter_contract:adapter_output_contract`
- `run413-kbo-osen-same-game-source`
  - `adapter_contract:adapter_output_contract`

Frozen classification:

`MIXED_ADAPTER_AND_SEMANTIC_FAILURE`

This is a definitive non-pass. It is not reinterpreted as a transient/provider-availability block.
There is no retry, prompt change, schema change, source/gold/scorer change, or threshold change for
this exact route.

## Artifact evidence

- artifact ID: `9707938165`
- artifact ZIP SHA-256:
  `7612efac4f5105f0b349bb1dbfdcd8a5faaeb841e6b95f470621e3ab12a500e6`
- internal qualification report SHA-256:
  `5d839980e468769da18610bddd2f680cdef48d65ed1bc92aeaf7b15fa2b8be58`

The downloaded ZIP was independently re-hashed and matched the GitHub Actions artifact digest. The
internal JSON report was independently hashed and re-read; it confirmed the exact 1/4 result and
case failures above.

## Isolation after result

The temporary one-shot CI lane was removed immediately after evidence capture. The ordinary
`.github/workflows/ci.yml` blob was restored to `72da8a9a2f8996ccdfb1af906c575911b25c28b0`.

The candidate remains qualification-only and is not selected or wired into production.

## Production and merge gates

The machine state remains unselected. The three migration blockers remain active. No fresh canary,
deploy, Push, or merge is authorized by this failed qualification.

PR #84 must remain OPEN / UNMERGED while another genuinely new eligible provider/model is sought
under the frozen V5 contract.
