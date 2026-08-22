# Insight Desk Phase 3 Bake-off

This directory is an evaluation harness only. It does not implement or restore the production content engine.

## Purpose

Compare candidate zero-cost semantic tools under role-specific, evidence-backed tests before any production architecture is frozen.

## Hard rules

- No paid API fallback.
- No legacy semantics, selection, synthesis, matcher, or publication code.
- Historical fixtures are evidence, not automatically valid gold labels.
- Generation failure must never be interpreted as event failure.
- Model/provider names do not receive preferential scoring.
- A provider without credentials is skipped, not replaced with a paid service.

## Corrected benchmark boundary

The original Phase 3 harness normalized 85 historical cases into one hard-scored set. Independent audit found that this overreached:

- 44 Run96 `true_negative_titles` were historical **selection negatives**, not neutral proof that the title described no material event. They mix generic context, low materiality, stale information, entity/query mismatch, and some genuine events. They are now preserved as `deferred_selection_evidence` and are not hard-scored until the new selection policy supplies the missing context.
- Run96 legacy `event_type` labels came from the retired engine, while candidate prompts were never given definitions for those labels. Exact-match event-type scoring is therefore disabled until a clean taxonomy is defined.
- The remaining 41 cases have direct semantic evidence for the fields being scored.

This correction preserves every historical failure example while preventing the old engine's hidden selection assumptions from becoming new-engine ground truth.

## Active lanes

1. `dataset.py` builds 41 semantically hard-scored cases and separately preserves 44 deferred selection cases.
2. `score.py` performs deterministic scoring only where the gold contract is semantically justified.
3. `local_nli.py` measures multilingual evidence-to-claim entailment using a local MIT-licensed NLI model.
4. `local_similarity.py` measures same-event candidate retrieval using a local multilingual embedding model; it is not an identity gate.
5. Provider adapters consume the same role-specific inputs.
6. A dedicated claim-verification lane is used to qualify any model proposed as an independent verifier.

## Current zero-cost candidates

- Groq Free: generation candidate; GPT-OSS 120B also remains a temporal/lifecycle auxiliary candidate.
- Cloudflare Workers AI Free: model-specific claim-verification candidate only; generic selection/event-type scores from the retired 85-case formulation are not architecture gates.
- Gemini API Free: rare third-opinion candidate only because the verified free quota is too small for core daily use.
- `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: local secondary evidence-to-claim verifier.
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: same-event candidate retrieval only.

External-provider execution is not required for the local lane and must not block it.
