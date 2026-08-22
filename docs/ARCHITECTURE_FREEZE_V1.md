# Insight Desk — Architecture Freeze V1

Status: `PHASE_4_ARCHITECTURE_FREEZE`
Date: 2026-08-23

This freeze ends tool/model R&D for the roles already proven by Phase 3 and freezes the clean-room boundaries implemented in Phase 4. It does not mean the acquisition pipeline or semantic engine is already implemented.

## 1. Non-negotiable system rules

1. Actual operating cost remains ₩0.
2. There is no paid fallback, automatic tier upgrade, prepaid credit path, or billing-triggered recovery action.
3. An item-level failure never becomes a global briefing abort.
4. Generation failure never deletes an already-established event.
5. An explicit identity contradiction cannot be overridden by embedding similarity or an LLM opinion.
6. Material-event truth and briefing selection are separate decisions.
7. Only supported claims may enter a published briefing entry.
8. Missing information remains missing; the renderer cannot manufacture confidence, history, watch-next, or other facts not present in a validated contract.

## 2. Frozen provider roles

### Groq GPT-OSS 20B
Role: primary Korean briefing generation / constrained structured generation.

Not allowed:
- sole fact verifier
- event identity final authority
- selection final gate

### Groq GPT-OSS 120B
Role: temporal/lifecycle auxiliary only.

It may help distinguish announced/prospective/resuming/completed states, but it is not an ownership or selection authority.

### Cloudflare Workers AI — Llama 3.3 70B
Model: `@cf/meta/llama-3.3-70b-instruct-fp8-fast`
Role: primary independent evidence→claim verifier only.

Dedicated role benchmark: 14/14 with zero provider errors.

Not allowed:
- generic material-event classifier
- legacy event-type classifier
- event identity gate
- selection policy gate

### Local mDeBERTa XNLI
Model: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`
Role: required secondary claim verifier.

Known limitation: prospective-departure vs already-departed produced a false entailment in the benchmark. Therefore it never acts alone as a publishing gate.

### Gemini 3.7 Flash Free
Role: optional rare third opinion only.
It is not a core dependency because the verified project Free Tier was too small for daily core use.

### multilingual MiniLM
Role: optional candidate retrieval/prefilter only.
It is forbidden as a same-event identity authority because a known different-date hard negative reached cosine 0.998932.

## 3. Verification policy

Primary: Cloudflare Llama 3.3 70B
Secondary: local mDeBERTa

- primary TRUE + secondary TRUE → `SUPPORTED`
- primary FALSE → `REJECTED`
- disagreement / missing / provider error → `INDETERMINATE`

A positive result from only one verifier is insufficient for publication.

## 4. Event identity

Identity proceeds in this order:

1. deterministic contradiction checks
2. candidate retrieval/similarity only if useful
3. optional semantic judgment only when genuinely ambiguous
4. default-safe result is separate events when ambiguity remains

An explicit date conflict forces separate events. The known 12-day vs 13-day baseball example must stay separate regardless of embedding or LLM similarity.

## 5. Selection

The engine must preserve the distinction:

`real/material event` ≠ `selected for this user's briefing`

A genuine event may be excluded because it is outside the configured interests, stale, redundant, or low-value without being relabeled as “not an event.” No single LLM decides the final selection policy.

## 6. Failure containment

Generation path:

`retry free path → available alternate zero-cost path when explicitly configured → extractive fallback`

Every generation recovery preserves the existing event.

Verification provider failure becomes an inconclusive check and is handled by the verification policy. It does not abort the briefing.

Identity ambiguity keeps candidates separate.

## 7. Acquisition selection for Phase 5

Already fixed foundation:
- NAVER Search API
- NAVER Search Trend API
- OpenDART
- KOSIS
- ECOS

Selected but not yet implementation-validated in Phase 5:
- Trafilatura as primary article extraction
- Playwright only as extraction fallback

These are not claims that Phase 5 is complete.

## 8. UI companion freeze

UI source branch: `ui-refoundation-pink-v2`
Reference commit at architecture freeze: `bb1fd3bab4a54bc43a152ff4dc6b62a34dd4e3c6`
Direction: Pink Editorial Intelligence / Soft Geometry V3.

The UI prototype and core→UI view-model mapping have passed isolated CI, but production CSS is still intentionally unchanged. The Event Ledger visual mode cannot be populated with real continuity until the engine has a persistent event-history contract.

## 9. Explicitly rejected architecture shortcuts

- restore legacy semantic engine
- generic LLM decides everything
- embedding similarity equals event identity
- generation mismatch deletes event
- renderer invents numeric confidence
- 44 old Run96 selection negatives become “not material event” gold
- undefined legacy event-type labels become exact scoring gate
- Cloudflare Llama used as generic selection classifier
- Gemini required for core daily operation
- any paid fallback

## 10. Phase 4 exit condition

Phase 4 may be declared complete only when:
- core contracts/failure boundaries pass CI
- identity/selection separation passes CI
- two-verifier aggregation passes CI
- zero-cost provider adapters pass CI
- this architecture freeze is machine-validated against the implementation

After that, the next phase is **Phase 5 — Acquisition Pipeline**, not more model R&D.
