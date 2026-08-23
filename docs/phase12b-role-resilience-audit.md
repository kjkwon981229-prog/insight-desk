# Phase 12B Role Resilience Audit

Status: IN PROGRESS — this document is not an acceptance declaration.

## Governing rule

Availability-sensitive tool roles must expose at least three zero-cost execution paths without
silently relaxing content correctness. Multiple models sharing one provider/account quota do not
count as independent external failure domains. Deterministic in-process contract stages are audited
separately because they do not consume provider quota; they must remain fail-closed and covered by
independent regression/validation gates rather than inventing divergent semantic authorities.

## Current role matrix

| Role | Current executable paths | Count/status | Acceptance blocker |
|---|---|---:|---|
| Discovery | NAVER Search API | 1 / BLOCKED | Add and validate two independent zero-cost discovery sources. |
| Article acquisition | urllib HTTP + Trafilatura; Playwright render + Trafilatura | 2 / BLOCKED | Add one independent extraction/acquisition path and regression-lock provenance equality. |
| Fact extraction | Kiwi deterministic extractor | 1 / BLOCKED | Audit safe redundant deterministic/local alternatives before activation; do not add an LLM final authority. |
| Generation | Groq GPT-OSS 20B; optional Gemini Flash-Lite; deterministic exact-source fallback | 3 / CODED | Gemini live canary must pass; Groq circuit/429 recovery must remain green. |
| Claim verification | Cloudflare Llama; optional Gemini Flash-Lite; local mDeBERTa | 3 tools / BLOCKED | Primary external failover canary must pass; local secondary still needs a validated fallback so mDeBERTa is not a single point of zero. |
| Rendering | deterministic Phase 8 renderer + feed validator contracts | in-process / AUDIT | No provider/quota dependency. Preserve one canonical renderer; redundancy is validation, not competing render semantics. |
| Deployment | GitHub Pages artifact/deploy path | external / AUDIT | Deployment does not decide content correctness; fail-closed preservation of the current site is required. |

## Rejected secondary NLI candidates

- `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`: positive 9/10, high-risk negative 5/10 — REJECTED.
- `MoritzLaurer/xlm-v-base-mnli-xnli`: positive 10/10, high-risk negative 9/10 — REJECTED; failed `n02_fx_direction` (6.1원 내림 vs 6.1원 오름).

Acceptance threshold is frozen at positive >= 9/10 and high-risk negative = 10/10. The threshold
must not be weakened to admit a fallback model.

## Current candidate under benchmark

- `MoritzLaurer/ernie-m-base-mnli-xnli`
- Same locked 20-case corpus and unchanged acceptance threshold.

## Provider invariants

1. Provider unavailable/rate-limited/quota-exhausted is not a content rejection.
2. Explicit semantic `False` remains a content decision and must not be escaped by availability failover.
3. Daily quota exhaustion opens the provider circuit for the run; rate limiting honors cooldown.
4. No paid fallback may activate automatically.
5. Exact-source deterministic fallback must be provably copied from cited EvidenceSpan bytes and must not depend on an external LLM.
6. PR heavy live production requires an explicit `[production-preflight]` exact-head marker.
7. Canonical acceptance still requires one exact head → one production run → one canonical artifact.

## Gates still open

- ERNIE-M local NLI benchmark verdict.
- Gemini synthetic positive/negative canary on current Interactions API contract.
- Local secondary failover factory/wiring after a candidate actually passes the locked benchmark.
- Discovery 3-path closure.
- Acquisition 3-path closure.
- Fact-extraction redundancy decision and regression proof.
- Exact-head full CI after all Phase 12B changes.
- One canonical `[production-preflight]` run only after all of the above are closed.
