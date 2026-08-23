# Phase 12B Role Resilience Audit

Status: IMPLEMENTATION COMPLETE FOR STATIC REVALIDATION — NOT A LIVE ACCEPTANCE DECLARATION
Date: 2026-08-23

## Governing rule

Availability-sensitive roles must have enough independent zero-cost recovery that one provider, quota bucket, runtime dependency, or optional credential cannot masquerade as content failure and collapse the feed to zero. Redundancy must not weaken semantic correctness.

Deterministic in-process stages are not required to invent competing semantic authorities. Their resilience may come from conservative alternate implementations plus independent validation. Generated prose remains more restrictive than exact-source fallback because generated paraphrases require semantic verification.

## Current role matrix

| Role | Executable paths | Current status | Remaining acceptance gate |
|---|---|---|---|
| Discovery | NAVER Search when configured → Bing News RSS → GDELT DOC | CODED + REGRESSION-LOCKED | Canonical live production must demonstrate usable discovery under real inputs. |
| Article acquisition | HTTP+Trafilatura → HTTP+Article/Main → Playwright+Trafilatura → Playwright+Article/Main | CODED + REGRESSION-LOCKED | Canonical live artifact/source audit. |
| Fact extraction | Kiwi → PeCab-backed exact-surface → conservative exact-surface parser | CODED + REGRESSION-LOCKED; PeCab runtime canary PASS | Canonical live semantic/event audit. |
| Generation | Groq GPT-OSS 20B → Gemini Flash-Lite → deterministic exact source | CODED + REGRESSION-LOCKED | Canonical live generation/audit behavior. |
| Generated-claim verification | logical primary: Cloudflare → Gemini; independent local secondary: mDeBERTa | CODED + REGRESSION-LOCKED | Canonical live behavior; generated text must still satisfy both logical slots. |
| Verification outage recovery | generated verification INDETERMINATE → deterministic exact-source downgrade | CODED + REGRESSION-LOCKED | Canonical live audit must show no unverifiable generated prose. |
| Exact-source verification | deterministic EvidenceSpan substring/provenance/preservation proof | CODED + REGRESSION-LOCKED | Same-artifact source/content audit. |
| Rendering | deterministic Phase 8 renderer + feed validator + artifact hash | STATIC PASS BEFORE FINAL CLEANUP | Fresh cleanup-head CI, then render QA on canonical artifact. |
| Deployment | one canonical PR artifact; Pages only after accepted merge/main production | PRESERVED | Merge remains blocked. |

## Local NLI benchmark verdict

Additional local semantic models were admitted only if they met the unchanged locked threshold:

- positive >= 9/10;
- high-risk negative = 10/10.

Measured candidates:

- `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`: 9/10 positive, 5/10 negative — REJECTED.
- `MoritzLaurer/xlm-v-base-mnli-xnli`: 10/10 positive, 9/10 negative — REJECTED.
- `joeddav/xlm-roberta-large-xnli`: 10/10 positive, 8/10 negative — REJECTED.
- `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: 10/10 positive, 10/10 negative — RETAINED.

No threshold was relaxed. Rejected local-fallback classes/tests and the temporary candidate benchmark harness are removed from the final candidate tree.

The local-secondary slot therefore remains one measured mDeBERTa authority. Its runtime/model loading is lazy and fail-soft: infrastructure failure yields an indeterminate local check, which cannot authorize generated prose. Phase 7 then downgrades the candidate to deterministic exact-source form when possible. This removes the zero-card availability single point without introducing a weaker local semantic authority.

## PeCab fact-extraction canary

PeCab was tested before production dependency activation on the same Python 3.12 family used by CI:

- run `32643504979`
- job `97204112956`
- artifact `9494239918`
- result `PECAB_SEMANTIC_FALLBACK_CANARY_ACCEPTED`

The route validates Korean case-particle/predicate structure and preserves exact source ranges. The final surface-only fallback remains stricter and rejects ambiguous/complex clauses rather than guessing.

## Provider and control-plane invariants

1. Provider unavailable/rate-limited/quota-exhausted/config-missing is not content rejection.
2. Explicit semantic `False` remains a semantic decision; failover does not reinterpret it as `True`.
3. Generated prose is never published on an unavailable verifier result.
4. Verification infrastructure failure may only trigger exact-source deterministic downgrade.
5. Exact-source fallback is literal cited evidence, not a paraphrase, and uses deterministic source proof.
6. Cloudflare proven daily-quota exhaustion opens its run-local circuit; later claims skip that route.
7. Generic 429 remains rate-limited unless the adapter proves a stronger quota state.
8. NAVER and Cloudflare multi-secret configurations are valid when both values are present or both absent; partial pairs fail fast.
9. Groq, NAVER, Cloudflare, and Gemini are not global workflow prerequisites when independent zero-cost fallback remains possible.
10. PR heavy production requires exact-head `[production-preflight]`.
11. One exact head → one canonical production execution → one canonical artifact.
12. No paid fallback exists.
13. Provider-routing diagnostics do not add article bodies, visible generated text, or secrets to logs.

## Last completed static evidence before final cleanup

Exact head `db7ee25b0e3cef0b8c0455c73e361c7e58116662` passed Infrastructure CI run `32644797487` (#1444):

- benchmark integrity PASS: `hard_scored=85 evidence_only=7 taxonomy=16 run96_positive=15 run96_tn=44`;
- Python: 250 total tests, 21 skipped, 229 non-skipped passed;
- Push Worker: 14/14 passed;
- npm audit: 0 vulnerabilities.

This is evidence for that exact head only. Subsequent cleanup removed rejected experiment code/jobs and updated these documents. Therefore a fresh exact-head CI is mandatory and the prior PASS is not promoted to the cleanup head.

## Gates still open

1. Fresh exact-head Infrastructure CI after final-tree cleanup.
2. Verify PR remains open/unmerged and capture the exact cleanup head SHA.
3. Freeze semantic/runtime code if the fresh static gate passes.
4. Create one minimal `[production-preflight]` exact-head marker commit.
5. Run exactly one canonical PR production execution.
6. Inspect the exact canonical artifact: run state, production audit, feed-quality report, and site bytes.
7. Full visible-card human audit.
8. Desktop/mobile render QA on those same artifact bytes.
9. Candidate acceptance only if all preceding gates pass.
10. Merge remains blocked until acceptance.
