# Phase 10 — Relevance DEFER Resolution Closure

## Decision

**COMPLETE / ACCEPTED**

This closure removes the production behavior where an event-level `RelevanceDecision.DEFER` was preserved only in audit output but collapsed to a boolean false in the legacy loop and immediately discarded.

The production path now performs a bounded source-expansion attempt for unresolved event relevance. Additional discovery candidates re-enter the normal `Source -> Relevance -> Event Understanding -> ...` pipeline from the beginning. The expansion owner never upgrades `DEFER` by itself.

## Ownership contract

- `ConfiguredLiteralRelevanceOwner` remains the single relevance decision owner.
- `BoundedRelevanceSourceExpansionLane` is orchestration only; it gathers additional source candidates and preserves the original `DEFER`.
- Discovery failure, missing structured query material, exhausted source expansion, or exhausted resolution acquisition budget never becomes `IRRELEVANT` or `RELEVANT` by default.
- Expanded candidates receive no semantic bypass and must satisfy the same freshness, source relevance, event relevance, Event Understanding, materiality, generation, verification, identity, and publication contracts as ordinary candidates.
- No article-, source-, domain-, team-, or topic-specific detector was introduced.

## Bounded budgets

The resolution lane uses independent bounds so that a source discovered to resolve a late `DEFER` is not starved by the ordinary acquisition budget:

```text
RELEVANCE_RESOLUTION_EXPANSION_LIMIT = 2 per topic
RELEVANCE_RESOLUTION_DISCOVERY_LIMIT = 3 per expansion
RELEVANCE_RESOLUTION_ACQUISITION_LIMIT = 2 per topic
```

Ordinary candidates still obey the existing normal acquisition budget. Resolution candidates are allowed to consume only the separate bounded resolution acquisition budget.

## RED evidence

Initial source-expansion RED:

```text
commit = e91776315929e7f96599c6b85d246f475f5731df
result = 1346 tests, 1 error, 23 skipped
failure = ModuleNotFoundError: insight_desk.production_relevance_resolution_v2
```

Independent acquisition-budget RED:

```text
commit = d5db33d31a427945f0059fbd26e425007f70dc74
result = 1354 tests, 1 error, 23 skipped
failure = missing RELEVANCE_RESOLUTION_ACQUISITION_LIMIT / budget contract
```

The second RED specifically requires a resolution candidate to remain processable after the ordinary acquisition count has already reached 8, while ordinary candidates remain blocked and resolution candidates stop at their own bound.

## GREEN evidence

GREEN production head:

```text
043e62984e4894e9d638f5b3c5d4071d2d15ae0e
```

Exact-head Infrastructure run:

```text
run = 33267454071
Python = 1356 tests / 23 skipped / 0 failed
benchmark = 85 / 7 / 16 / 15 / 44
Push Worker = 20 / 20
npm audit = 0 vulnerabilities
historical production replay = SUCCESS
Phase 6 correctness + recall = SUCCESS
```

Normal Daily safety run:

```text
run = 33267454073
pr_live_gate = SUCCESS
build = SKIPPED
deploy = SKIPPED
push_notify = SKIPPED
```

## Fresh canary

Marker-only preflight head:

```text
de40d3a0e697ce58de998b065b3e40990c2af617
```

It points to the exact same tree as the GREEN production head. Compare result:

```text
files = []
```

Fresh production run:

```text
run = 33267545976
build = SUCCESS
deploy = SKIPPED
push_notify = SKIPPED
PHASE11_PRODUCTION_RUN status=SUCCESS publish=true entries=3
FEED_QUALITY_PASS story_count=3 publication_contract_version=2
PUBLICATION_IDENTITY_VALID publications=3
```

Artifact:

```text
artifact_id = 9719194013
zip_sha256 = 56ab4780a6e69bca2fbadba93161954ecc9df37ac2e3a1f1a75e0352ab6bc25a
html_sha256 = 0ba5cb480a879ec43a9c3819b0f1786383fd8be63981fc6886f9f69e3258bf60
publication_digest = 95d9d3bd3ef735789aa4491e0a9ac81c5b4bb33d436af0f348cb9c7f4e84956e
```

Feed validator:

```text
max_headline_chars = 30
max_summary_chars = 141
visible_source_links = 3
all reported quality issue counters = 0
```

## Production proof that the independent budget was used

The fresh artifact reports ordinary acquisition already at the normal limit while additional resolution acquisitions still occurred:

```text
ai_tech:
  acquisition_attempts = 8
  relevance_resolution_expansions = 2
  relevance_resolution_candidates = 6
  relevance_resolution_acquisitions = 2

kbo_hanwha:
  acquisition_attempts = 8
  relevance_resolution_expansions = 2
  relevance_resolution_candidates = 1
  relevance_resolution_acquisitions = 1

psat_recruitment:
  acquisition_attempts = 8
  relevance_resolution_expansions = 2
  relevance_resolution_candidates = 3
  relevance_resolution_acquisitions = 2
```

This is the production evidence that the new resolution candidates are not merely discovered and queued: they are actually acquired after the ordinary acquisition budget has been exhausted.

When the separate resolution budget is exhausted, the audit records a `defer` with reason `relevance_defer:resolution_acquisition_budget_exhausted`; it does not silently reclassify the event.

## Human/source acceptance

The three visible publications were manually checked against their sources:

1. Economy — the selected 2026-08-30 source is centrally about the Bank of Korea's consecutive rate increases and the rationale for pre-emptive tightening; the visible summary is source-central, not a secondary background sentence.
2. K-POP — SF9 `TENACITY` 9-region KPOP top-10 and 6-region POP top-10 figures match the source.
3. PSAT — the statement that PSAT will be used from 2027 as the first-stage examination for national 5th/7th-grade recruitment and other examinations matches the Personnel Management Ministry's official 2026-08-27 announcement.

Previously observed P1 classes remain absent, including historical marketing metrics, secondary KBO lineup/preview facts, stale sports captions, definition-only PSAT cards, non-Hanwha KBO admissions, deep-body economy background promotion, and raw/full article-body publication.

```text
P0 = 0
P1 = 0
```

## Preserved external limitations

This phase does not change the frozen provider qualification state. No new Event Understanding provider was searched, selected, or wired.

`ECOS_API_KEY` also remains absent from the GitHub Actions environment. ECOS code/config/workflow wiring exists, but ECOS was `not_configured` in the fresh run. KOSIS and OpenDART remain configured.

## Final Phase 10 decision

**The event-level relevance uncertainty path now performs bounded additional-source acquisition instead of treating `DEFER` as a terminal boolean false. The production replay, recall gate, fresh canary, source audit, and publication safety checks pass. Phase 10 is accepted.**
