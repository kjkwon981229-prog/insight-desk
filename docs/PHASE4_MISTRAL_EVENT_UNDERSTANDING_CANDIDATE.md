# PHASE 4 — Dedicated Mistral Event Understanding Candidate

Status: `NOT_QUALIFIED` / NO PRODUCTION WIRING

Candidate provider: Mistral API
Candidate model: `mistral-large-2512` (Mistral Large 3)

## Candidate boundary

This candidate is separate from the existing Groq generation and Cloudflare/Gemini/local-NLI verification responsibilities. It remains qualification-only and is not exported through the production provider package surface or wired into production.

The bounded qualification reused the existing frozen Event Understanding prompt, JSON schema, semantic topic scopes, and four historical exact-source excerpt cases without per-case tuning.

## Valid one-shot qualification result

After `MISTRAL_API_KEY` was deliberately configured, exact-head run `33050426588` evaluated Mistral Large 3 at head `71d4c88731ae86a0084ef34862ac1c2d7bc30bbd`.

GitHub Actions masked the configured credential and the qualification entered the real provider-call path. The result was:

```text
status = NOT_QUALIFIED
evaluated_cases = 4
passed_cases = 0
failure_classification = ContractError
```

All four frozen cases failed with `provider_or_contract_error:ContractError`:

- `run413-bok-kbs-rate-decision`
- `run413-bok-kmib-outlook-child`
- `run413-kpop-alphadriveone-actor-preserved`
- `run413-kbo-osen-same-game-source`

This is a valid bounded semantic/contract qualification failure. It is not a credential-preflight failure and it does not authorize prompt, schema, gold-fixture, or per-case tuning followed by another run.

Evidence artifact:

- artifact id: `9637447266`
- digest: `sha256:a84835d17ad5b9dae372ba381e4809c682b74cee63c7b661a15bdd0b051475fa`

The earlier run `33047255995` remains historical evidence only that the credential was previously absent; it is superseded for Mistral candidate status by the valid configured run above.

## Frozen consequence

Mistral Large 3 is frozen as `NOT_QUALIFIED` for `event_understanding_v1`.

The provider inventory returns to `NO_ELIGIBLE_EXISTING_PROVIDER`, `selected_event_understanding_provider` remains null, and `production_wired` remains false.

The one-shot GitHub Actions candidate job is removed after this result is frozen, so Mistral cannot be retried automatically.

No production marker, fresh discovery, PWA build, deploy, or Push is authorized by this qualification result.

A future Event Understanding provider must be a deliberately selected independent candidate and must use the same frozen bounded qualification contract. Existing verification/generation/temporal owners may not be silently repurposed. Independently, the PHASE 4 migration gate remains closed until its three legacy semantic bypasses are removed after a provider has first achieved `MINIMUM_COMPATIBILITY_PASS`.
