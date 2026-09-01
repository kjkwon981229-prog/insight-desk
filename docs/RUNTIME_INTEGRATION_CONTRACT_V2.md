# Runtime Integration Contract V2

This document classifies code-declared external integrations by their current production role. An
API key being present means **configured**, not validated. Live validation requires a successful,
sanitized contract probe or a recorded production call.

## Current production contract

| Integration | Owner | Activation | Semantic authority | Validation route |
| --- | --- | --- | --- | --- |
| NAVER News Search | Discovery | When both NAVER credentials exist | None | One-item read-only search probe plus production call audit |
| Bing News RSS | Discovery | Always | None | One-item read-only RSS probe plus production call audit |
| GDELT DOC | Discovery | Explicit `GDELT_DISCOVERY_ENABLED=true` only | None | One-item English query probe; disabled by default |
| Publisher HTTP + Trafilatura | Acquisition | Per selected candidate | Exact acquired bytes only | Production acquisition method/failure audit |
| Playwright + Trafilatura | Acquisition fallback | When static acquisition is insufficient | Exact acquired bytes only | Production acquisition method/failure audit |
| ECOS | Authoritative enrichment | Enabled config and credential | May add a bound official fact; cannot rewrite the event | One-row read-only probe when configured |
| KOSIS | Authoritative enrichment | Enabled config and credential | May add a bound official fact; cannot rewrite the event | One-row read-only probe when configured |
| OpenDART | Authoritative enrichment | Enabled config and credential | May add a bound official fact; cannot rewrite the event | One-row read-only probe when configured |
| Push Worker health | Publication delivery | When the Worker URL exists | None | Read-only `/health` publication-binding-v2 probe |
| Web Push send | Publication delivery | Main deployment only, with send token | None | Bound READY/FAILURE response in the main workflow |
| GitHub Actions / Artifacts / Pages | Build and deployment | Workflow event dependent | None | Workflow/job/artifact/deployment evidence |

The visible semantic authority is the one exact canonical source proposition. External semantic
providers do not participate in the exact-source visible path.

## Installed but not active on the visible path

- Groq generation, Cloudflare Workers AI verification, Gemini verification, and local NLI are
  constructed compatibility routes but receive zero visible-path calls under the V2 exact-source
  contract.
- NAVER Search Trend has a client method but no production caller.
- Cerebras, Cohere, Hugging Face Router, Mistral, OpenRouter, and the additional Groq/Gemini model
  adapters are bounded qualification code, not production runtime authorities.
- `config/authoritative_sources.json.public_sources` is reserved configuration. No production
  caller consumes those website entries, so their presence must not be reported as an active API.

## GDELT disposition

GDELT remains available as an explicit opt-in adapter but is not in the default Korean-news route
set. Accepted canary run `33431471866` recorded 13 calls, 13 errors, and zero contributed candidates.
Default activation therefore added latency without recall and could not be called operationally
validated. This is an integration-scope decision only; it does not add a news-content rule or move
semantic authority.

## Audit rules

`scripts/audit_runtime_integrations.py` performs bounded read-only probes during an explicitly marked
PR production preflight. It records only integration identifiers, status, call count, and sanitized
exception class. Credentials, response bodies, article text, and provider error detail are excluded.

A configured operational integration that fails its probe fails the marked preflight. An optional
integration without credentials is reported as `NOT_CONFIGURED` and cannot affect the canonical
event or publication. A provider outside the visible path is reported as `NOT_ON_VISIBLE_PATH` and
is not called merely to improve an availability score.
