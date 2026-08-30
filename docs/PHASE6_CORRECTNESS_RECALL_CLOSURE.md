# Phase 6 Correctness and Recall Closure

Status: **COMPLETE / RECOVERABLE_HISTORICAL_SCOPE**

Exact code GREEN head: `781650a8b3bc10743c737c861691f8662c30ca73`

GitHub Actions run: `33246740065`

## Gate result

The Phase 6 correctness/recall gate runs the Phase 5 production replay and scores the resulting publication manifest against the recoverable historical source set.

Exact accepted metrics:

```text
evidence_scope = recoverable_real_url_plus_exact_source_bytes_only
expected_publishable = 3
expected_suppressed_same_event = 1
actual_publications = 3
correctly_published = 3
correctly_suppressed_same_event = 1
publication_recall = 1.0
publication_precision = 1.0
same_event_suppression_recall = 1.0
parent_child_identity_ok = true
canonical_bundle_validated = true
publication_digest_bound = true
provenance_integrity_ok = true
historical_full_body_coverage = unavailable_not_in_denominator
```

The negative controls also require the scorer to fail when an expected source is missing or when the suppressed same-event BOK child is incorrectly republished.

## Scope boundary

This is not a claim of correctness over historical full publisher article bodies because those bytes were not preserved by the original artifacts. Missing historical full-body coverage is explicitly excluded rather than silently counted as PASS.

Phase 7 must supply the fresh acquisition/canary evidence needed to test the live source-to-publication path and the historical oversized-body UI failure class against a newly acquired source.

## Safety boundary

No fresh live, deploy, Push, provider search, provider promotion, or merge was performed to close Phase 6.
