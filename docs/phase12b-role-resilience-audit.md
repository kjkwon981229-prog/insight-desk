# Phase 12B–12E Production Acceptance Audit

Status: CANONICAL LIVE PREFLIGHT CANDIDATE — NOT AN ACCEPTANCE DECLARATION
Date: 2026-08-24

## Governing rules

1. Provider availability is not content correctness.
2. Article relevance is not child-event relevance.
3. Publisher reuse/legal boilerplate is not a material news event.
4. One visible briefing may contain each normalized headline at most once.
5. One visible briefing may contain each normalized summary at most once.
6. One exact PR head produces one canonical production execution and one canonical artifact.
7. Automated PASS never replaces full visible-card human audit or render QA.
8. No paid provider path may activate automatically.

## Preserved provider-resilience state

Phase 12B remains regression-locked:

- discovery: NAVER when configured → Bing News RSS → GDELT DOC;
- acquisition: HTTP+Trafilatura → HTTP+Article/Main → Playwright+Trafilatura → Playwright+Article/Main;
- fact extraction: Kiwi → PeCab-backed exact-surface → conservative exact-surface parser;
- generation: Groq GPT-OSS 20B → Gemini Flash-Lite when configured → deterministic exact source;
- generated-claim primary slot: Cloudflare → Gemini when configured;
- local secondary: measured mDeBERTa only;
- exact-source fallback: deterministic EvidenceSpan proof, not external LLM availability.

Provider unavailability/rate limiting/quota exhaustion/config absence never becomes semantic rejection. Explicit semantic `False` is never converted to support. Generated prose is not authorized without the required generated-prose verification contract.

Local NLI threshold was not weakened. Measured alternatives remained rejected; mDeBERTa retained 10/10 positive and 10/10 high-risk negative on the locked comparison. PeCab runtime canary remains run `32643504979`, artifact `9494239918`, result `PECAB_SEMANTIC_FALLBACK_CANARY_ACCEPTED`.

## Canonical #107 — automated PASS, human topic audit FAIL

Head `d2f256592f9635ce520d4cb194366749700eb79a`, Daily Production #107 / run `32645280407`, artifact `9494738555`.

Human audit found article-level topic relevance inherited by unrelated child events: K-POP family-center/400-booth content, Doosan/Lotte Kwak Bin content under KBO·Hanwha, LEET under PSAT, and a non-AI tourism contest under AI·Tech.

Verdict: canonical failure evidence; not acceptable.

## RC-12 — event-local topic binding

Repair:

- article-level relevance remains only a coarse admission filter;
- each material child event traverses `event.fact_ids → fact.evidence_ids → exact EvidenceSpan.text`;
- missing/out-of-event evidence fails closed;
- configured topic literals must occur in that event-local cited evidence;
- computed `event_relevant` is passed into Phase 6;
- irrelevant children are skipped before provider verification cost;
- Korean BTS alias `방탄소년단` was added alongside `BTS` only.

Static RC-12 head `9278289d01a29783dc5e48516af6ef04107a6dcf` passed CI #1464 / run `32646069518`: 259 total Python tests, 21 skipped, 238 non-skipped passed; benchmark integrity PASS; Push Worker 14/14; npm audit 0 vulnerabilities.

## Canonical #111 — RC-12 live PASS, human duplicate audit FAIL

Head `e6ac7013f0af01aaa2ccc43a14a760c71074c223`, Daily Production #111 / run `32646176678`, artifact `9494978109`, digest `sha256:0ed00d31d5c5c1ea3930b2e5561c561d8899f0da015997bd75de1c9d46c62d80`.

The four #107 false-topic patterns disappeared. Human audit nevertheless found two economy cards with the same normalized visible headline `27일 한국은행 기준금리 결정 주목`; their summaries differed only by a surface ending.

Verdict: automated PASS / RC-12 live behavior PASS / human duplicate audit FAIL.

## RC-13 — visible headline uniqueness

Frozen product invariant:

> ONE NORMALIZED VISIBLE HEADLINE MAX ONE CARD PER BRIEFING.

Three defenses were added without changing Phase 6 semantic identity:

1. production publish boundary skips duplicate normalized headlines before `published.append` and before topic-slot consumption;
2. renderer keeps only the first normalized headline;
3. artifact validator independently hard-fails `FEED_QUALITY_DUPLICATE_HEADLINE` and reports `duplicate_headlines`.

Static RC-13 head `004d0f997f263eaab552a807829f60b524ca2a24` passed CI #1480 / run `32647067413`: 264 total, 21 skipped, 243 non-skipped passed; benchmark integrity PASS; Push Worker 14/14; npm audit 0 vulnerabilities.

## Canonical #119 — automated PASS, human audit FAIL

Head:

`6f5c33e47ed283961d086537db6e7d1a2d29d79c`

Canonical production:

- Daily Production #119 / run `32647175879`
- artifact `9495236054`
- artifact digest `sha256:5afad7acec765bdc83a81e8973e775886e42428fb399303295f0f3e6dc3ad220`
- 12 visible cards
- artifact `site/index.html` SHA-256 `c5f6a63df1662eb32fbfa03a070ba3b8c07079e4c61569c1cd53fda10acfd08d`
- automated validator PASS
- `duplicate_headlines=0`
- `duplicate_content=0`
- duplicate source/source-content: 0
- PSAT forbidden hits: 0

Independent artifact inspection confirmed the run-state HTML hash, feed-quality HTML hash, and actual ZIP `site/index.html` hash were identical.

RC-12 remained healthy: prior false-topic patterns did not return. RC-13 also worked exactly as specified: no duplicate normalized headline survived.

Full visible-card human audit nevertheless found two new P1 defects.

### P1-A — duplicate event survived headline variation

Two economy cards had different headlines:

- `27일 한국은행 기준금리 결정에 이목 집중`
- `27일 한국은행 기준금리 결정에 관심`

but their normalized visible summaries were identical:

`오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠립니다.`

They describe the same Bank of Korea August 27 rate-decision event. RC-13's headline-only surface identity was therefore insufficient.

### P1-B — publisher reuse notice became an AI news card

The first AI·Tech card was:

- headline: `AI 학습용 데이터 무단 사용 책임`
- summary: `뉴스1 콘텐츠를 인공지능(AI) 학습용 데이터로 사용하는 것을 포함하여, 사전허가없이 무단 복사, 배포, 전재, 판매하면 민·형사상의 책임이 따를 수 있습니다.`

This is a publisher copyright/reuse notice, not a reported news event. Exact evidence and grammatical predicate checks were both satisfied, so the old material gate incorrectly treated syntactically valid publisher boilerplate as material news.

Two weaker centrality observations remain P2 watch items, not P1 findings: an AI-related event where AI is not the whole parent event, and a KBO standings card where Hanwha is a causal condition rather than the foreground subject. Neither is used to widen the current fix.

Verdict: #119 AUTOMATED PASS / HUMAN AUDIT FAIL / NOT ACCEPTABLE.

## RC-14 — visible summary uniqueness

Root cause:

The publication surface guaranteed unique normalized headlines but did not independently guarantee unique normalized summaries. A same-event pair could therefore vary the headline while emitting the same summary.

Frozen product invariant:

> ONE NORMALIZED VISIBLE HEADLINE OR SUMMARY MAX ONE CARD PER BRIEFING.

This remains a deterministic publication-surface rule, not a general semantic same-event classifier. Phase 6 identity is unchanged; no fuzzy threshold, embedding similarity, LLM merge authority, or new provider was added.

Closure uses the same three defenses as headline uniqueness:

1. production boundary: duplicate normalized summary is skipped before `published.append` and before `published_entries += 1`, so it does not consume the topic slot or source/content identity;
2. renderer: duplicate normalized summary is omitted item-locally;
3. artifact validator: duplicate normalized summary hard-fails as `FEED_QUALITY_DUPLICATE_SUMMARY` and `duplicate_summaries` is emitted in the quality report.

Regression RED was established before implementation on the exact #119-shaped pair: distinct Bank of Korea headlines with the same normalized summary.

## RC-15 — publisher notice boilerplate is not material news

Root cause:

The material-event gate previously required exact cited evidence, literal fact surfaces, and an explicit verbal predicate. A publisher copyright/reuse notice can satisfy all three while still not being a news event.

The repair is intentionally narrow and occurs at the material gate, not acquisition, so raw article provenance/body is not mutated.

A cited text is classified as publisher-notice boilerplate only when all three high-precision conditions hold:

1. permission/unauthorized cue: `무단`, `사전허가없이`, or `사전 허가 없이`;
2. at least two restriction/use terms among `복사`, `배포`, `전재`, `재배포`, `판매`;
3. a legal/consequence cue among `책임`, `금지`, `저작권`.

Such an item returns `DEFER / PUBLISHER_NOTICE_BOILERPLATE` before normal material-predicate acceptance.

A positive control remains material: `법원이 AI 기업의 무단 데이터 복제에 대해 손해배상 책임을 인정했다.` It has a real reported actor/action and does not satisfy the publisher-notice restriction-term conjunction.

Kiwi extraction logic, Trafilatura, source body, topic config, generation, verification policy, and Phase 6 identity remain unchanged.

## RC-14/15 regression and static evidence

Regression-only head:

`1f9f6f631f631f5c28d303ae13b8c31af2a61980`

Infrastructure CI #1492 / run `32647941200` deliberately failed:

- 267 total tests
- 21 skipped
- publisher notice still MATERIAL — FAIL
- same normalized summary rendered twice — FAIL
- validator did not raise duplicate-summary failure — FAIL
- `duplicate_summaries` metric missing — ERROR
- production summary guard missing — ERROR

Companion Daily Production #124 / run `32647941202` was gate-only; build/deploy/push skipped.

Exact implementation/static head:

`25c5d61da9f9046f91548c90b54612b96004d5e7`

Implementation after the RED head is limited to four runtime files:

- `insight_desk/semantic/material.py`
- `insight_desk/rendering.py`
- `scripts/phase11_daily_production.py`
- `scripts/validate_feed_artifact.py`

Infrastructure CI #1500 / run `32648167662` — SUCCESS:

- benchmark integrity: `hard_scored=85 evidence_only=7 taxonomy=16 run96_positive=15 run96_tn=44`
- Python: 267 total, 21 skipped, 246 non-skipped passed
- Push Worker: 14/14 passed
- npm audit: 0 vulnerabilities

Companion Daily Production #128 / run `32648167770` was gate-only: build, deploy, and push all skipped. No provider-heavy production was consumed on the static head.

## Canonical-run invariants for this marker

1. This marker commit may modify this audit document only.
2. Runtime/semantic tree must remain identical to static head `25c5d61...`.
3. Exact marker-head Infrastructure CI must remain green.
4. Exactly one marker-head canonical PR production run may execute.
5. Same artifact bytes must pass run-state/audit/feed-quality/hash consistency checks.
6. `duplicate_headlines=0` and `duplicate_summaries=0` are both required.
7. Full visible-card human audit must verify #107 false-topic patterns, #111/#119 duplicate patterns, and #119 publisher-notice pattern are absent.
8. Desktop/mobile render QA must inspect those exact same artifact bytes.
9. Candidate acceptance may occur only after every gate above passes.
10. Merge remains blocked until candidate acceptance.

## Gates still open

1. Prove marker head differs from `25c5d61...` only by this audit document.
2. Confirm exact marker-head static CI.
3. Complete exactly one canonical PR production execution.
4. Inspect exact run-state, production audit, feed-quality report, site bytes, and hashes.
5. Full visible-card source/topic/content/duplicate/boilerplate human audit.
6. Desktop/mobile render QA on the exact same artifact bytes.
7. Candidate acceptance only if all preceding gates pass.
8. Merge remains blocked until acceptance.
