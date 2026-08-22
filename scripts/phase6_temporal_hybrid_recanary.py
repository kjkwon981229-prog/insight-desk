from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, TemporalState
from insight_desk.providers import GROQ_120B, GroqFreeClient
from insight_desk.semantic import TemporalResolutionSource, resolve_temporal_state

ROOT = Path(__file__).resolve().parents[1]
RUN90 = ROOT / "benchmarks" / "run90_temporal.json"
RUN97 = ROOT / "benchmarks" / "run97_generation.json"


def load_cases() -> list[tuple[str, dict, TemporalResolutionSource]]:
    run90 = json.loads(RUN90.read_text(encoding="utf-8"))["cases"]
    run97 = [
        case
        for case in json.loads(RUN97.read_text(encoding="utf-8"))["cases"]
        if "temporal_state" in case.get("gold", {})
    ]
    if len(run90) != 7 or len(run97) != 6:
        raise SystemExit(
            f"locked hybrid canary expected run90=7/run97=6, found {len(run90)}/{len(run97)}"
        )
    return (
        [("run90", case, TemporalResolutionSource.DETERMINISTIC) for case in run90]
        + [("run97", case, TemporalResolutionSource.AUXILIARY) for case in run97]
    )


def main() -> int:
    if not os.environ.get("GROQ_API_KEY", "").strip():
        raise SystemExit("GROQ_API_KEY is not configured")

    auxiliary = GroqFreeClient.from_env(GROQ_120B)
    cases = load_cases()
    failures: list[str] = []
    source_counts = {source.value: 0 for source in TemporalResolutionSource}

    for index, (suite, case, expected_source) in enumerate(cases, start=1):
        case_id = case["id"]
        text = f'{case["input"]["title"]}\n{case["input"]["lead"]}'
        expected_state = TemporalState(case["gold"]["temporal_state"].lower())
        article_id = f"recanary-article-{index}"
        evidence_id = f"recanary-evidence-{index}"
        fact_id = f"recanary-fact-{index}"
        event_id = f"recanary-event-{index}"

        span = EvidenceSpan(
            evidence_id=evidence_id,
            article_id=article_id,
            field=EvidenceField.BODY,
            start=0,
            end=len(text),
            text=text,
        )
        fact = EventFact(
            fact_id=fact_id,
            subject="locked-recanary-subject",
            action="locked-recanary-action",
            evidence_ids=(evidence_id,),
        )
        event = CandidateEvent(
            event_id=event_id,
            topic_id=case.get("input", {}).get("topic_id", "cross_domain_temporal"),
            fact_ids=(fact_id,),
            article_ids=(article_id,),
        )
        result = resolve_temporal_state(
            event,
            fact,
            {evidence_id: span},
            auxiliary=auxiliary,
        )
        source_counts[result.source.value] += 1
        passed = (
            result.state is expected_state
            and result.source is expected_source
            and result.error_code is None
            and result.auxiliary_used is (expected_source is TemporalResolutionSource.AUXILIARY)
        )
        actual_state = result.state.value if result.state is not None else "UNRESOLVED"
        print(
            f"TEMPORAL_HYBRID_RECANARY suite={suite} case={case_id} "
            f"expected_state={expected_state.value} actual_state={actual_state} "
            f"expected_source={expected_source.value} actual_source={result.source.value} "
            f"result={'PASS' if passed else 'FAIL'}"
        )
        if not passed:
            failures.append(
                f"{case_id}: expected={expected_state.value}/{expected_source.value} "
                f"actual={actual_state}/{result.source.value} error={result.error_code}"
            )

    print(
        "TEMPORAL_HYBRID_RECANARY_SUMMARY "
        f"total={len(cases)} pass={len(cases) - len(failures)} fail={len(failures)} "
        f"deterministic={source_counts['deterministic']} auxiliary={source_counts['auxiliary']} "
        f"unresolved={source_counts['unresolved']} model={GROQ_120B} "
        f"checked_at={datetime.now(timezone.utc).isoformat()}"
    )
    if failures:
        for failure in failures:
            print("TEMPORAL_HYBRID_RECANARY_FAILURE " + failure)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
