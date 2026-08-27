# PHASE 4 — Dedicated Mistral Event Understanding Candidate

Status: `QUALIFICATION_BLOCKED_CREDENTIAL` / NO PRODUCTION WIRING

Candidate provider: Mistral API
Candidate model: `mistral-large-2512` (Mistral Large 3)

## Candidate boundary

This candidate is separate from the existing Groq generation and Cloudflare/Gemini/local-NLI verification responsibilities. It remains qualification-only and is not exported through the production provider package surface or wired into production.

The bounded qualification reuses the existing frozen Event Understanding prompt, JSON schema, semantic topic scopes, and four historical exact-source excerpt cases without per-case tuning.

## Credential preflight result

The corrected exact-head candidate run was `33047255995` at head `fadb04ae40160fea6ca8b56fc1149487a74509c6`.

The GitHub Actions environment exposed an empty `MISTRAL_API_KEY`. The qualification harness therefore stopped before constructing a provider call and reported:

```text
status = NOT_CONFIGURED
evaluated_cases = 0
passed_cases = 0
```

This is not a semantic qualification failure. Mistral Large 3 has therefore **not** been marked `NOT_QUALIFIED`.

Evidence artifact:

- artifact id: `9636139336`
- digest: `sha256:bad5a540efefefd7700682bc20360f4040809c9d7f18a1085531239f4dda23f3`

## Frozen consequence

The provider selection state records Mistral Large 3 as `QUALIFICATION_BLOCKED_CREDENTIAL` and the inventory as `CANDIDATE_QUALIFICATION_BLOCKED`.

The candidate cannot be selected and `production_wired` remains false. The one-shot GitHub Actions candidate job is removed after this evidence is frozen, so the same candidate is not retried automatically.

A later semantic qualification is authorized only after `MISTRAL_API_KEY` is deliberately configured and a new explicit candidate commit re-enables exactly one run of the same frozen four-case contract. No prompt, schema, gold fixture, or semantic scoring change is implied by credential setup.

No production marker, fresh discovery, PWA build, deploy, or Push is authorized by this credential-block closure.
