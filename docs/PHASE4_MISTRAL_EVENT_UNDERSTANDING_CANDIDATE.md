# PHASE 4 — Dedicated Mistral Event Understanding Candidate

Status: QUALIFICATION-ONLY / NO PRODUCTION WIRING

Candidate provider: Mistral API
Candidate model: `mistral-large-2512` (Mistral Large 3)

This candidate is separate from the existing Groq generation and Cloudflare/Gemini/local-NLI verification responsibilities. It is intentionally not exported from the production provider package surface and is not wired into production.

The bounded qualification reuses the existing frozen Event Understanding prompt, JSON schema, semantic topic scopes, and four historical exact-source excerpt cases without per-case tuning.

Credential behavior is fail-closed:

- if `MISTRAL_API_KEY` is absent, qualification stops before any provider call and records `NOT_CONFIGURED` with zero evaluated cases;
- if configured, the exact `mistral-large-2512` model is evaluated once;
- no alias such as `mistral-large-latest` is used because an alias can move between model versions;
- no production marker, fresh discovery, PWA build, deploy, or Push is authorized by this candidate commit.

The candidate does not alter `config/event_understanding_provider_status_v2.json`. That frozen selection state changes only after the one-shot result is known.
