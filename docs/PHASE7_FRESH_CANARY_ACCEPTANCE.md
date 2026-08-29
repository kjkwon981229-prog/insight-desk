# Phase 7 — Fresh Canary Acceptance

Status: **COMPLETE**

This phase closes the fresh-acquisition correctness gate for the current canonical publication path. It does **not** authorize deployment, push notification, provider activation, or merge.

## Acceptance contract

Phase 7 required one fresh production acquisition on an exact GREEN tree, followed by human/source/render review. Acceptance required:

- production success on the current pipeline;
- publication-contract and identity validation;
- no raw/source article-body projection into visible cards;
- no context/background fact promoted as the article's source-central event;
- no stale dated retrospective promoted as current news;
- no static/copular definition promoted as a news event;
- required topic binding preserved at the event level;
- compact standalone headline and summary;
- visible source link preserved;
- P0 = 0 and P1 = 0 under human/source review.

## Structural regressions closed before final canary

### Explicit event-date / context ownership

The deterministic bridge now preserves a single explicit current-sentence date into `EventFact.event_date`. Static copular definitions are classified as context/background, and clearly stale date-only events are not promoted as current source-central events.

This closed the previously observed background-statistic, PSAT-definition, and stale sports-retrospective failure classes.

### Required-intent event binding

`required_intent_terms` is now a true event-level requirement. Broad `intent_anchors` cannot substitute for a required subject/topic binding. Topics without required terms may still use their broad anchors.

Regression evidence included a broad sports event that was otherwise structurally valid but lacked the required team binding; it must remain DEFER rather than publish as relevant.

### Deep-body source centrality

A deep-body event can no longer prove source centrality through an object-only title overlap. Outside the lead, a specific actor must itself be title-bound before the compatibility owner can classify that event as the source-central PRIMARY event.

The centrality ranking remains unchanged; only the proof threshold was corrected. If the extractor misses the actual lead event, the article is held rather than promoting a deep-body background fact.

## Exact GREEN evidence

GREEN code head before marker-only preflight:

`1e292e822743e6c2d132190191a6175d21e33da5`

Infrastructure run:

`33257008878`

Results:

- Python: **1345 tests / 23 skipped / 0 failed**
- clean-room benchmark: **85 / 7 / 16 / 15 / 44**
- Push Worker: **20 / 20**
- npm audit: **0 vulnerabilities**
- historical production replay: **SUCCESS**
- Phase 6 correctness + recall gate: **SUCCESS**

Normal Daily run on the same GREEN head:

`33257008823`

- PR live gate: SUCCESS
- build: SKIPPED
- deploy: SKIPPED
- push_notify: SKIPPED

## Marker-only tree equivalence

Final preflight head:

`3532deb0a3ab93844a94e9899625ea9b62cf4945`

Comparison against GREEN `1e292e822743e6c2d132190191a6175d21e33da5` returned:

```text
files = []
```

The final production canary therefore ran on the same repository tree as the validated GREEN code.

The marker-only head also passed Infrastructure, historical production replay, and Phase 6 correctness + recall.

## Final fresh production canary

Workflow run:

`33257069687`

Exact head:

`3532deb0a3ab93844a94e9899625ea9b62cf4945`

Production result:

```text
PHASE11_PRODUCTION_RUN status=SUCCESS publish=true entries=3
PHASE11_STATE status=SUCCESS publish=true entries=3
```

Feed-quality validator:

```text
story_count=3
publication_contract_version=2
max_headline_chars=36
max_summary_chars=137
headline_summary_collisions=0
context_dependent_headlines=0
context_dependent_summaries=0
visible_metadata_issues=0
non_event_analytical_summaries=0
conditional_analytical_summaries=0
malformed_visible_texts=0
mixed_event_summaries=0
stale_dated_contexts=0
stale_sports_retrospectives=0
topic_binding_violations=0
duplicate_headlines=0
duplicate_summaries=0
duplicate_content=0
duplicate_sources=0
duplicate_source_content=0
stale_source_urls=0
visible_source_links=3
psat_forbidden_hits=0
```

Publication identity:

```text
briefing_id=daily-20260829T232052+0900
publication_digest=0e9ec14f4d36d9a90d677ea9d77fe9dc91dbc92c3a9c579424e97f4c810b5733
publications=3
```

Canonical PR artifact:

```text
artifact_id=9716250930
zip_sha256=ce94961982142e98ae060ee936a156f95e9a73d83f9ee71f9ff655f785c0f750
html_sha256=768967f608d2db880542a9fc35275f23a52211b34a76a30ddd90b4b4bce68485
```

Preflight safety outcome:

- deploy: **SKIPPED**
- push_notify: **SKIPPED**

## Human / source / visible-card audit

The final artifact contained exactly three visible cards:

1. **K-POP — SF9 / `TENACITY` chart result**
   - actor and album preserved;
   - 9-region KPOP Top 10 and 6-region POP Top 10 figures are current and independently corroborated;
   - concise generated summary; source link preserved.

2. **KBO·Hanwha — NC 11–4 Hanwha**
   - current 29 August game result;
   - Hanwha is directly bound to the event, eliminating the previous unrelated-team admission class;
   - concise generated summary; source link preserved.

3. **PSAT recruitment — 2027 first-stage usage**
   - current 27 August Personnel Ministry policy announcement;
   - the card expresses the policy change/event rather than a static PSAT definition;
   - concise generated summary; source link preserved.

The earlier economy background-event candidate disappeared entirely from the final artifact after the deep-body centrality correction. Economy produced zero published entries in the final canary.

No visible card exposed a source article body or multi-paragraph article prose. The longest summary was 137 characters.

### Final human acceptance

```text
P0 = 0
P1 = 0
```

The following previously observed failure classes were absent from the final artifact:

- historical/background `6,901` statistic promoted as current news;
- PSAT static/definition sentence promoted as an event;
- stale `7일` KBO retrospective promoted as current;
- KBO/Hanwha topic containing a non-Hanwha game;
- deep-body object-only background event promoted as source-central;
- oversized/raw source-body projection into the PWA.

## Remaining boundaries

Phase 7 completion does **not** change the provider qualification state:

```text
qualification_contract_status = AWAITING_PROVIDER_QUALIFICATION
provider_inventory_status = CANDIDATE_QUALIFICATION_BLOCKED
selected_event_understanding_provider = null
production_wired = false
full_production_correctness_claimed = false
production_rewire_allowed = false
```

Provider research remains intentionally stopped. Frozen provider failures/non-passes remain frozen.

No deployment, push notification, or merge is authorized by this phase.

## Handoff

**Phase 7 is COMPLETE. Phase 8 — human/source/render acceptance closure and final PWA/Desktop/Mobile review — is NEXT.**

Phase 9 / MERGE_READY remains blocked until Phase 8 completes and the final P0/P1 acceptance state is preserved.