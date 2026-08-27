# PHASE 4 — OpenRouter Nemotron Event Understanding Candidate

Status: `QUALIFICATION_PREPARED / CREDENTIAL_NOT_CONFIGURED / NO PRODUCTION WIRING`

Candidate provider: OpenRouter
Candidate model: `nvidia/nemotron-3-super-120b-a12b:free`

## Candidate boundary

This is a new qualification-only Event Understanding candidate. It is not exported through the production provider package surface and is not wired into production.

The model id is frozen to the explicit `:free` variant. The random `openrouter/free` router is forbidden for this qualification, and the paid model variant without `:free` is also forbidden.

The request sets `provider.require_parameters = true`, so OpenRouter may only use an endpoint that supports the requested structured-output parameters. There is no cross-model fallback.

## Why this candidate is eligible for qualification

Current OpenRouter documentation provides a Free plan with free-model API access and a base limit of 50 requests/day. The selected Nemotron 3 Super free model is listed at zero token price and supports structured outputs via JSON Schema in `response_format`.

Current references:

- OpenRouter pricing: https://openrouter.ai/pricing
- Nemotron 3 Super free model: https://openrouter.ai/nvidia/nemotron-3-super-120b-a12b:free
- OpenRouter provider routing: https://openrouter.ai/docs/guides/routing/provider-selection

The 50-request/day ceiling is not yet accepted as a production capacity claim. If this model first passes semantic qualification, source-backed replay must prove the Event Understanding call budget fits the free-plan limit before production wiring can be accepted.

## Frozen qualification contract

The candidate reuses, without modification:

- `tests/fixtures/event_understanding_qualification_v1.json`
- `config/semantic_topics_v2.json`
- `EVENT_UNDERSTANDING_SCHEMA_V1`
- the existing source-range evidence binding
- the existing scorer and all four historical exact-source excerpt cases

No fresh news, production marker, PWA build, deploy, or Push is involved.

Missing `OPENROUTER_API_KEY` is a preflight state only: `NOT_CONFIGURED`, zero evaluated cases, and no provider call. A missing credential must not be recorded as `NOT_QUALIFIED`.

## Current execution state

No one-shot GitHub Actions candidate lane is installed by this preparation commit. This prevents an automatic zero-call qualification attempt before the repository owner deliberately configures `OPENROUTER_API_KEY`.

`config/event_understanding_provider_status_v2.json` is intentionally unchanged. The machine selection truth remains `NO_ELIGIBLE_EXISTING_PROVIDER`, selected provider null, and `production_wired = false` until a real one-shot qualification result exists.

After the credential is deliberately configured, exactly one explicit `[semantic-candidate:openrouter-nemotron]` commit may enable the bounded qualification. A semantic or contract failure is frozen as `NOT_QUALIFIED`; it does not authorize per-case prompt/schema/gold tuning or retry loops.

Even a `MINIMUM_COMPATIBILITY_PASS` does not by itself authorize production wiring. The separate PHASE 4 migration gate must still remove the three legacy semantic bypasses before the qualified owner can be wired.
