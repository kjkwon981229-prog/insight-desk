# Phase 12B/12C/12D Production Acceptance Audit

Status: CANONICAL LIVE PREFLIGHT CANDIDATE — NOT AN ACCEPTANCE DECLARATION
Date: 2026-08-23

## Governing rules

1. Provider availability is not content correctness.
2. Article relevance is not child-event relevance.
3. One visible briefing must not contain duplicate normalized headlines.
4. One exact PR head produces one canonical production execution and one canonical artifact.
5. Automated PASS never replaces full visible-card human audit or render QA.
6. No paid provider path may activate automatically.

## Provider-resilience state

Phase 12B remains regression-locked:

- discovery: NAVER when configured → Bing News RSS → GDELT DOC;
- acquisition: HTTP+Trafilatura → HTTP+Article/Main → Playwright+Trafilatura → Playwright+Article/Main;
- fact extraction: Kiwi → PeCab-backed exact-surface → conservative exact-surface parser;
- generation: Groq GPT-OSS 20B → Gemini Flash-Lite when configured → deterministic exact source;
- generated-claim primary slot: Cloudflare → Gemini when configured;
- local secondary: measured mDeBERTa only;
- exact-source fallback: deterministic EvidenceSpan proof, not external LLM availability.

Provider unavailability/rate limiting/quota exhaustion/config absence never becomes semantic rejection. Explicit semantic `False` is never converted to support. Generated prose is not authorized without the required generated-prose verification contract.

Local NLI threshold was not weakened. Measured alternatives were rejected:

- multilingual MiniLM: 9/10 positive, 5/10 high-risk negative;
- XLM-V: 10/10 positive, 9/10 negative;
- XLM-R: 10/10 positive, 8/10 negative;
- mDeBERTa: 10/10 positive, 10/10 negative — retained.

PeCab runtime canary evidence remains:

- run `32643504979`
- job `97204112956`
- artifact `9494239918`
- `PECAB_SEMANTIC_FALLBACK_CANARY_ACCEPTED`

## Canonical #107 — automated PASS, human topic audit FAIL

Head:
`d2f256592f9635ce520d4cb194366749700eb79a`

- Daily Production #107 / run `32645280407`
- artifact `9494738555`
- digest `sha256:b61f8965aabbfbe90552cdaf23a538f9382b3e7eb39a38d8875f740a0d201743`
- 13 visible cards
- automated feed validation PASS

Human audit found article-level topic relevance inherited by unrelated child events, including K-POP family-center/400-booth content, Doosan/Lotte Kwak Bin content under KBO·Hanwha, LEET under PSAT, and a non-AI tourism contest under AI·Tech.

Verdict: canonical failure evidence; not acceptable.

## RC-12 — event-local topic binding

Root cause:
`Phase6SelectionContext(topic_relevant=True)` allowed every child event from an article that had passed coarse article relevance to inherit topic authority.

Repair:

- article-level relevance remains only a coarse admission filter;
- each material child event traverses `event.fact_ids → fact.evidence_ids → exact EvidenceSpan.text`;
- missing/out-of-event evidence fails closed;
- configured topic literals must occur in that event-local cited evidence;
- computed `event_relevant` is passed into Phase 6;
- irrelevant children are skipped before provider verification cost;
- Korean BTS alias `방탄소년단` was added alongside `BTS` only.

Static RC-12 head `9278289d01a29783dc5e48516af6ef04107a6dcf` passed CI #1464 / run `32646069518`: 259 total Python tests, 21 skipped, 238 non-skipped passed; benchmark integrity PASS; Push Worker 14/14; npm audit 0 vulnerabilities.

## Canonical #111 — RC-12 PASS, human duplicate audit FAIL

Head:
`e6ac7013f0af01aaa2ccc43a14a760c71074c223`

- Daily Production #111 / run `32646176678`
- artifact `9494978109`
- artifact digest `sha256:0ed00d31d5c5c1ea3930b2e5561c561d8899f0da015997bd75de1c9d46c62d80`
- 12 visible cards
- `site/index.html` SHA-256 `364f638d91a7ebf716fbdb71f75085f57c9cb79f57ad4a8128c05623cf827c4b`
- automated validator PASS
- duplicate content/source/source-content: 0
- generation accepted: 12
- provider errors: 10
- exact-source/verification recovery fallback: 0

RC-12 outcome:

- all four #107 canonical false-topic patterns were absent;
- `event_topic_relevance` was exercised 15 times to reject unrelated child events;
- PSAT produced zero cards rather than publishing the prior LEET false positive.

Human audit nevertheless found one P1 product defect:

- economy card `event-cccf98a85350551a9274`
- economy card `event-f15279288a716eba4417`
- both visible headlines normalized to exactly `27일 한국은행 기준금리 결정 주목`;
- summaries differed only in the surface ending `쏠리고 있습니다` versus `쏠립니다`;
- source-group and body hashes were distinct, so source-level dedup correctly considered them separate articles.

This is not proof that Phase 6 should semantically merge arbitrary cross-source events. Existing identity policy deliberately refuses deterministic same-event merges without an explicit semantic judgment. The narrower product defect is that the visible duplicate contract required the full `(headline, summary)` tuple to match, allowing an identical headline to appear twice when the summary varied trivially.

Two weaker centrality observations were retained as P2 watch items, not P1 false-topic findings:

- AI·Tech book-festival card included AI experience/exhibition programs in its exact event evidence but AI was not the entire festival's central subject;
- KBO·Hanwha Lotte-standings card explicitly depended on Hanwha's same-day loss but foregrounded Lotte.

Neither was treated as RC-12 failure because the visible event evidence itself contained the configured topic binding.

Verdict: #111 automated PASS / RC-12 live behavior PASS / HUMAN DUPLICATE AUDIT FAIL. Not acceptable.

## RC-13 — visible headline uniqueness

Root cause:

Phase 8 renderer deduplicated only the normalized `(headline, summary)` pair. Artifact validation enforced the same effective surface condition. Therefore two verified cards with an identical normalized headline could both survive if their summaries differed.

Frozen product invariant:

> ONE NORMALIZED VISIBLE HEADLINE MAX ONE CARD PER BRIEFING.

This is a publication-surface invariant, not a claim that deterministic Phase 6 has solved general semantic event identity.

Closure uses three defenses:

1. Production publish boundary
   - normalize the final verified headline using whitespace collapse + casefold;
   - if already published, record `visible_identity / normalized_headline_already_published` and skip;
   - perform the guard before `published.append` and before `published_entries += 1`, so a duplicate does not consume a topic slot;
   - source/content identities are not consumed by a skipped duplicate, allowing search to continue for a distinct candidate.
2. Renderer
   - keep only the first normalized visible headline even if summaries differ.
3. Artifact validator
   - independently count/reject duplicate normalized headlines as `FEED_QUALITY_DUPLICATE_HEADLINE`;
   - emit `duplicate_headlines` in the feed-quality report.

General Phase 6 semantic identity remains unchanged. No fuzzy headline threshold, embedding similarity, LLM merge authority, or new provider was added.

## RC-13 regression evidence

Regression RED was demonstrated before implementation:

- CI #1472 / run `32646825173`
- 263 tests total, 21 skipped
- renderer showed both `event:rate-a` and `event:rate-b` for the same normalized Bank of Korea headline;
- validator did not raise `FEED_QUALITY_DUPLICATE_HEADLINE`;
- validator lacked the `duplicate_headlines` report field.

Implementation is limited to:

- `scripts/phase11_daily_production.py`
- `insight_desk/rendering.py`
- `scripts/validate_feed_artifact.py`
- corresponding regression tests.

## Frozen Phase 12D static evidence

Exact static head:

`004d0f997f263eaab552a807829f60b524ca2a24`

Compared with #111 marker head `e6ac7013f0af01aaa2ccc43a14a760c71074c223`, changed runtime files are limited to the three RC-13 files above; remaining changes are the associated tests.

Infrastructure CI:

- #1480 / run `32647067413` — SUCCESS
- benchmark integrity: `hard_scored=85 evidence_only=7 taxonomy=16 run96_positive=15 run96_tn=44`
- Python: 264 total, 21 skipped, 243 non-skipped passed
- Push Worker: 14/14 passed
- npm audit: 0 vulnerabilities

Companion Daily Production #118 / run `32647067415` was gate-only: build, deploy, and push all skipped. No provider-heavy live production was consumed on the static head.

## Canonical-run invariants

1. This marker commit may modify this audit document only.
2. Runtime/semantic tree must remain identical to static head `004d0f9...`.
3. Exact marker-head Infrastructure CI must remain green.
4. Exactly one marker-head canonical PR production run may execute.
5. Same artifact bytes must pass run-state/audit/feed-quality/hash consistency checks.
6. `duplicate_headlines` must be zero.
7. Full visible-card human audit must verify both #107 false-topic patterns and #111 duplicate pattern are absent.
8. Desktop/mobile render QA must inspect those same artifact bytes.
9. Merge remains blocked until every acceptance gate passes.

## Gates still open

1. Prove marker head differs from `004d0f9...` only by this audit document.
2. Confirm marker-head static CI.
3. Complete one canonical PR production execution.
4. Inspect the exact canonical artifact and hashes.
5. Full visible-card source/topic/content/duplicate human audit.
6. Desktop/mobile render QA on the exact same artifact.
7. Candidate acceptance only if all above pass.
8. Merge remains blocked until acceptance.
