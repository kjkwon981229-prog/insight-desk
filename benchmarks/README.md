# Insight Desk Clean-room Benchmark

This directory contains evaluation assets only. It must never contain or import legacy Insight Desk engine implementation code.

## Purpose

Reconstruct historical failure evidence as provider-neutral benchmark data before the new engine is designed.

The benchmark is allowed to preserve:

- source titles/leads used to reproduce a failure class;
- expected event/non-event labels;
- expected semantic invariants such as event type, subject, action, object, polarity and temporal state;
- expected ownership/clustering relationships;
- forbidden semantic transformations and known Korean grammar defects.

The benchmark must not preserve:

- legacy selection, synthesis, matcher, qualification or publication code;
- legacy regex or keyword acceptance rules;
- implementation-specific event signatures as executable truth;
- title blacklists as production logic;
- any rule that turns a local generation failure into global publication failure.

## Source lineage

Historical evidence was reconstructed from the pre-reset repository state at commit `8f4098935010d65bbda77db766ff660ac3399b19`, principally Run89/90/92/94/95/96/97 replay fixtures and tests.

The source commit is provenance only. No code from that engine is imported by this benchmark.

## Current suites

- `run96_recall_precision.json`: 15 confirmed positive event groups and 44 confirmed true-negative titles.
- `run90_temporal.json`: duration/date/lifecycle/cancellation distinctions.
- `run92_ownership.json`: same-event clustering versus cross-event ownership separation.
- `run94_95_semantic.json`: mixed-focus, context-noun and malformed-lineup failures.
- `run97_generation.json`: planned/completed preservation, material-object preservation and Korean grammar defects.

## Hard benchmark principles

1. A benchmark case describes expected meaning, not a preferred implementation.
2. String equality alone is never sufficient evidence of semantic correctness.
3. A generation failure is not an event failure.
4. A local case failure must not suppress unrelated verified events.
5. Provider-specific prompts and scores belong in later bake-off output, not in the gold dataset.
6. All production candidates must be evaluated against the same gold data.

## Validation

Run:

```bash
python benchmarks/validate.py
```

The validator checks only benchmark integrity: JSON validity, unique IDs, taxonomy membership, declared suite counts and required gold fields. It contains no content-engine semantics.
