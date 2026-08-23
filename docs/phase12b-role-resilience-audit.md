# Phase 12B/12C Role Resilience and Topic-Binding Audit

Status: CANONICAL LIVE PREFLIGHT CANDIDATE — NOT AN ACCEPTANCE DECLARATION
Date: 2026-08-23

## Governing rule

Availability-sensitive roles must have enough independent zero-cost recovery that one provider, quota bucket, runtime dependency, or optional credential cannot masquerade as content failure and collapse the feed to zero. Redundancy must not weaken semantic correctness.

Publication relevance is a separate invariant: article-level topical relevance may admit an article for semantic extraction, but it may not authorize every child event from that article. Every publishable child event must independently bind to its configured topic using only the exact evidence cited by that event's facts.

Generated prose remains more restrictive than exact-source fallback because generated paraphrases require semantic verification.

## Current role matrix

| Role | Executable paths | Current status | Remaining acceptance gate |
|---|---|---|---|
| Discovery | NAVER Search when configured → Bing News RSS → GDELT DOC | CODED + REGRESSION-LOCKED | Canonical live production must demonstrate usable discovery under real inputs. |
| Article acquisition | HTTP+Trafilatura → HTTP+Article/Main → Playwright+Trafilatura → Playwright+Article/Main | CODED + REGRESSION-LOCKED | Canonical live artifact/source audit. |
| Fact extraction | Kiwi → PeCab-backed exact-surface → conservative exact-surface parser | CODED + REGRESSION-LOCKED; PeCab runtime canary PASS | Canonical live semantic/event audit. |
| Event-topic binding | event.fact_ids → fact.evidence_ids → exact EvidenceSpan text → configured topic literals | CODED + REGRESSION-LOCKED | Canonical live human/topic audit must show no article-level relevance inheritance. |
| Generation | Groq GPT-OSS 20B → Gemini Flash-Lite → deterministic exact source | CODED + REGRESSION-LOCKED | Canonical live generation/audit behavior. |
| Generated-claim verification | logical primary: Cloudflare → Gemini; independent local secondary: mDeBERTa | CODED + REGRESSION-LOCKED | Canonical live behavior; generated text must still satisfy both logical slots. |
| Verification outage recovery | generated verification INDETERMINATE → deterministic exact-source downgrade | CODED + REGRESSION-LOCKED | Canonical live audit must show no unverifiable generated prose. |
| Exact-source verification | deterministic EvidenceSpan substring/provenance/preservation proof | CODED + REGRESSION-LOCKED | Same-artifact source/content audit. |
| Rendering | deterministic Phase 8 renderer + feed validator + artifact hash | STATIC PASS | Render QA on the canonical artifact. |
| Deployment | one canonical PR artifact; Pages only after accepted merge/main production | PRESERVED | Merge remains blocked. |

## RC-7 provider-availability closure

Provider availability and semantic content verdict remain separate dimensions.

1. Provider unavailable/rate-limited/quota-exhausted/config-missing is not content rejection.
2. Explicit semantic `False` remains a semantic decision; failover does not reinterpret it as `True`.
3. Generated prose is never published on an unavailable verifier result.
4. Verification infrastructure failure may only trigger exact-source deterministic downgrade.
5. Exact-source fallback is literal cited evidence, not a paraphrase, and uses deterministic source proof.
6. Cloudflare proven daily-quota exhaustion opens its run-local circuit; later claims skip that route.
7. Generic 429 remains rate-limited unless the adapter proves a stronger quota state.
8. NAVER and Cloudflare multi-secret configurations are valid when both values are present or both absent; partial pairs fail fast.
9. Groq, NAVER, Cloudflare, and Gemini are not global workflow prerequisites when independent zero-cost fallback remains possible.
10. No paid fallback exists.

## Local NLI benchmark verdict

Additional local semantic models were admitted only if they met the unchanged locked threshold: positive >= 9/10 and high-risk negative = 10/10.

Measured candidates:

- `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`: 9/10 positive, 5/10 negative — REJECTED.
- `MoritzLaurer/xlm-v-base-mnli-xnli`: 10/10 positive, 9/10 negative — REJECTED.
- `joeddav/xlm-roberta-large-xnli`: 10/10 positive, 8/10 negative — REJECTED.
- `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`: 10/10 positive, 10/10 negative — RETAINED.

No threshold was relaxed. The local-secondary slot remains the measured mDeBERTa authority. Runtime/model loading is fail-soft; infrastructure failure cannot authorize generated prose and may only lead to deterministic exact-source downgrade.

## PeCab fact-extraction canary

PeCab was tested before production dependency activation on the same Python 3.12 family used by CI:

- run `32643504979`
- job `97204112956`
- artifact `9494239918`
- result `PECAB_SEMANTIC_FALLBACK_CANARY_ACCEPTED`

The route validates Korean case-particle/predicate structure and preserves exact source ranges. The final surface-only fallback remains stricter and rejects ambiguous/complex clauses rather than guessing.

## Canonical production #107 — automated PASS, human audit FAIL

Previous marker head:

`d2f256592f9635ce520d4cb194366749700eb79a`

Canonical Daily Production:

- run `32645280407` / #107
- artifact `9494738555`
- artifact digest `sha256:b61f8965aabbfbe90552cdaf23a538f9382b3e7eb39a38d8875f740a0d201743`
- generated entries: 13
- automated feed-quality validation: PASS
- duplicate content/source/source-content: 0
- provider errors: 0

That artifact was rejected during full visible-card human audit. Confirmed/strong false-topic publications included:

- K-POP child event about family centers / 400 booths with no K-POP event binding;
- KBO·Hanwha child events about Doosan/Lotte starter Kwak Bin with no Hanwha event binding;
- PSAT·civil-service child event about a law-school/LEET mock exam rather than PSAT recruitment;
- AI·Tech child event about a general tourism open-innovation contest with no AI event binding.

Therefore #107 is canonical failure evidence, not an acceptance artifact.

## RC-12 — article relevance inherited by unrelated child events

Root cause:

The production runner correctly applied `topic_relevant(title=article.title, body=article.body, topic=topic)` as an article-level admission filter, but every semantic child event then entered Phase 6 with `Phase6SelectionContext(topic_relevant=True)`. Once an article contained one configured topic literal, unrelated material events from the same article could inherit that relevance and reach publication.

RC-12 definition:

> Article-level topical relevance was incorrectly inherited by child events without event-local topic binding.

The repair is narrow:

1. Keep article-level `topic_relevant` only as a coarse discovery/acquisition guard.
2. For each material child event, traverse `event.fact_ids`.
3. Resolve each fact and only its `evidence_ids`.
4. Build event-local relevance text solely from those exact cited `EvidenceSpan.text` values.
5. Fail closed on missing facts, missing spans, or spans outside the event's article IDs.
6. Require configured topic literals on that event-local text.
7. Pass the computed `event_relevant` into `Phase6SelectionContext` instead of a hardcoded `True`.
8. Record rejected children as `event_topic_relevance` skips before verification/provider spending.

The only topic-literal addition is the Korean BTS alias `방탄소년단`, paired with existing `BTS`, to preserve a confirmed K-POP positive binding without broadening unrelated categories.

## RC-12 regression lock

The locked event-local corpus includes canonical negatives:

- family-center / 400-booth child event must not bind to K-POP;
- Doosan/Lotte Kwak Bin event must not bind to KBO·Hanwha;
- law-school LEET mock exam must not bind to PSAT·civil-service;
- general tourism open-innovation contest must not bind to AI·Tech.

Positive controls remain required:

- Gyeongbuk AI ecosystem forum → AI·Tech;
- group EP release → K-POP;
- `방탄소년단` tour event → K-POP;
- LG vs Hanwha game → KBO·Hanwha;
- Ministry of Personnel 5th-grade PSAT schedule → PSAT·civil-service;
- Bank of Korea base-rate event → Economy.

The production-source regression also forbids `topic_relevant=True,` and requires `topic_relevant=event_relevant,`.

## Frozen Phase 12C static evidence

Exact static head:

`9278289d01a29783dc5e48516af6ef04107a6dcf`

Changes after the RC-12 RED regression head `6656802c3e54075372bfa43a6ccc29718afc3311` are limited to:

- `scripts/phase11_daily_production.py`: event-local binding/wiring;
- `config/topics.json`: `방탄소년단` alias only.

Infrastructure CI:

- run `32646069518` / #1464 — SUCCESS
- benchmark integrity: `hard_scored=85 evidence_only=7 taxonomy=16 run96_positive=15 run96_tn=44`
- Python: 259 total tests, 21 skipped, 238 non-skipped passed
- Push Worker: 14/14 passed
- npm audit: 0 vulnerabilities

Companion Daily Production run `32646069480` / #110 executed only the PR preflight gate; build, deploy, and push were all skipped because the static head was not marked for live production. No provider-heavy production was consumed at that gate.

## Canonical-run invariants

1. PR heavy production requires exact-head `[production-preflight]`.
2. One exact head → one canonical production execution → one canonical artifact.
3. The marker commit may change this audit document only; runtime/semantic code remains identical to static head `9278289...`.
4. Same-artifact automated validation, human topic/content audit, and desktop/mobile render QA are all required.
5. Merge remains blocked until all gates pass.

## Gates still open

1. Confirm this marker head differs from `9278289...` only by this audit document.
2. Confirm exact marker-head Infrastructure CI remains green.
3. Complete exactly one canonical PR production execution for this marker head.
4. Inspect exact run state, production audit, feed-quality report, and site bytes from the canonical artifact.
5. Repeat full visible-card source/topic/content human audit; specifically verify all #107 false-topic patterns are absent.
6. Desktop/mobile render QA on those same artifact bytes.
7. Candidate acceptance only if every preceding gate passes.
8. Merge remains blocked until acceptance.
