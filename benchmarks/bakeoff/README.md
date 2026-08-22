# Insight Desk Phase 3 Bake-off

This directory is an evaluation harness only. It does not implement or restore the production content engine.

## Purpose

Compare candidate zero-cost semantic tools under the same benchmark inputs and scoring rules before any production architecture is frozen.

## Hard rules

- No paid API fallback.
- No legacy semantics, selection, synthesis, matcher, or publication code.
- Provider output is judged against the Phase 2 clean-room benchmark, not against old implementation behavior.
- Generation failure must never be interpreted as event failure.
- Model/provider names do not receive preferential scoring.
- A provider without credentials is skipped, not replaced with a paid service.

## Lanes

1. `dataset.py` normalizes all 85 hard-scored Phase 2 cases into one bake-off contract.
2. `score.py` performs deterministic scoring where the gold contract permits it.
3. `local_nli.py` measures multilingual evidence-to-claim entailment using a local MIT-licensed NLI model.
4. `local_similarity.py` measures same-event candidate retrieval using a local multilingual embedding model.
5. Provider adapters are added separately and must consume the same normalized cases.

## Current zero-cost candidates

- Groq Free: structured extraction/generation candidate.
- Cloudflare Workers AI Free: independent semantic verifier candidate.
- Gemini API Free: independent comparison/fallback candidate.
- `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: local NLI verifier candidate.
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: local same-event retrieval candidate.

External-provider execution is not required for the local lane and must not block it.
