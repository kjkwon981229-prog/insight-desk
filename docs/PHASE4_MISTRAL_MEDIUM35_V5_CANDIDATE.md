# Phase 4 — Mistral Medium 3.5 Event Understanding V5 Candidate

Status: ONE-SHOT QUALIFICATION ARMED — RESULT NOT YET FROZEN

## Exact candidate route

- provider: Mistral AI
- qualification provider id: `mistral_medium35`
- exact model id: `mistral-medium-3-5`
- endpoint: `/v1/chat/completions`
- credential: existing `MISTRAL_API_KEY`
- production wiring: none
- active qualification protocol: V5
- required result: 4/4 only

This is a genuinely new exact provider/model route. Historical Mistral evidence is frozen on
`mistral-large-2512`; that route is not retried, reclassified, or used as active V5 evidence.

## Current provider evidence checked before implementation

Mistral's current official documentation identifies Mistral Medium 3.5 as:

- model id `mistral-medium-3-5`;
- GA, v26.04;
- 256k context;
- supporting Structured Outputs on `/v1/chat/completions`;
- supporting Chat Completions on `/v1/chat/completions`.

Official references checked on 2026-08-28:

- `https://docs.mistral.ai/models/mistral-medium-3-5-26-04`
- `https://docs.mistral.ai/studio/conversations/structured-output`
- `https://docs.mistral.ai/api`

Mistral documentation also states that Studio/API access is enabled in Free mode by default with no
credit card required, subject to usage and rate limits, and that Free mode uses included monthly
usage. An API key consumes the quota and plan of its Workspace/Organization rather than carrying a
separate plan identity.

Official references checked on 2026-08-28:

- `https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key`
- `https://docs.mistral.ai/admin/billing-usage/usage-limits`
- `https://docs.mistral.ai/admin/identity-access/api-keys`

Mistral Medium 3.5 also has normal metered pricing. This project does not authorize paid fallback or
a pay-as-you-go activation. The bounded qualification is permitted only against already included
zero-cost usage available to the existing Workspace. If the first one-shot call is rejected for
quota, billing, payment, or model availability, that result is frozen as evidence. No payment is
enabled and no retry is performed.

## Existing credential evidence

Historical GitHub Actions run `33094503683` showed `MISTRAL_API_KEY` configured for the repository.
That run evaluated the different frozen route `mistral-large-2512`; it returned four transient
provider failures. This candidate does not retry that exact route.

The presence of the secret proves configuration only. It does not pre-claim that the current
Workspace has enough included quota for this new model. The one-shot qualification is the bounded
execution evidence for that question.

## Frozen V5 contract

No candidate-specific semantic contract change is allowed. This candidate receives the canonical
V5 contract exactly as frozen in:

- `tests/fixtures/event_understanding_qualification_v5.json`
- `insight_desk/event_understanding_adapter_v4.py`
- `scripts/qualify_event_understanding_provider_v5.py`

The candidate must use the same:

- four historical exact-source cases;
- source handoff and metadata;
- semantic gold;
- scorer and distinct event-draft matching;
- deterministic exact-text evidence binding;
- deterministic output invariants;
- acceptance threshold of 4/4.

No source, gold, scorer, acceptance, prompt, or V5 schema is changed for this model.

## Isolation boundary

The candidate implementation is qualification-only:

- `insight_desk/providers/mistral_medium35.py`
- `scripts/qualify_mistral_medium35_v5.py`
- `tests/test_mistral_medium35_v5_event_understanding_provider.py`
- this document

The historical `insight_desk/providers/mistral.py` remains frozen. The new client is not exported
from `insight_desk.providers`, not selected in the provider registry, and not wired into production.
The wrapper scope-registers `mistral_medium35` only inside the V5 runner and restores the canonical
runner state afterward.

## Preflight evidence before the one-shot trigger

Qualification-only candidate head `40e7db524889ab14fe588accae9244775fa00886`:

- Infrastructure run `33180165827`: SUCCESS
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

The staging commit deliberately omitted the trigger token. The only next permitted execution is the
single trigger commit carrying `[semantic-v5-candidate:mistral-medium-3-5]`. The qualification job
still depends on ordinary Infrastructure and historical replay succeeding on that exact trigger
head before the provider is called.

## One-shot execution gate

The first valid execution result is frozen. There is no provider rerun and no candidate-specific
tuning after the result. The temporary lane is removed immediately after evidence capture.

## Production and merge gates

A V5 4/4 result proves minimum compatibility only. It does not by itself remove the three migration
blockers, wire production, authorize a fresh canary, deploy, Push, or merge. PR #84 remains open and
unmerged until the downstream migration and publication acceptance sequence is separately proven.
