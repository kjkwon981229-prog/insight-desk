from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    TemporalState,
)
from insight_desk.providers import GROQ_120B, GroqFreeClient
from insight_desk.semantic import TemporalResolutionSource, resolve_temporal_state

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "run90_temporal.json"


def main() -> int:
    if not os.environ.get("GROQ_API_KEY", "").strip():
        raise SystemExit("GROQ_API_KEY is not configured")

    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if len(cases) != 7:
        raise SystemExit(f"locked canary expected 7 cases, found {len(cases)}")

    auxiliary = GroqFreeClient.from_env(GROQ_120B)
    failures: list[str] = []

    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        text = f'{case["input"]["title"]}\n{case["input"]["lead"]}'
        expected = TemporalState(case["gold"]["temporal_state"].lower())
        article_id = f"canary-article-{index}"
        evidence_id = f"canary-evidence-{index}"
        fact_id = f"canary-fact-{index}"
        event_id = f"canary-event-{index}"

        evidence = EvidenceSpan(
            evidence_id=evidence_id,
            article_id=article_id,
            field=EvidenceField.BODY,
            start=0,
            end=len(text),
            text=text,
        )
        fact = EventFact(
            fact_id=fact_id,
            subject="locked-canary-subject",
            action="locked-canary-action",
            evidence_ids=(evidence_id,),
            temporal_state=None,
        )
        event = CandidateEvent(
            event_id=event_id,
            topic_id=case["input"]["topic_id"],
            fact_ids=(fact_id,),
            article_ids=(article_id,),
        )
        result = resolve_temporal_state(
            event,
            fact,
            {evidence_id: evidence},
            auxiliary=auxiliary,
        )
        passed = (
            result.state is expected
            and result.source is TemporalResolutionSource.AUXILIARY
            and result.auxiliary_used
            and result.error_code is None
        )
        actual = result.state.value if result.state is not None else "UNRESOLVED"
        print(
            f"TEMPORAL_CANARY case={case_id} expected={expected.value} "
            f"actual={actual} result={'PASS' if passed else 'FAIL'}"
        )
        if not passed:
            failures.append(
                f"{case_id}: expected={expected.value} actual={actual} error={result.error_code}"
            )

    print(
        f"TEMPORAL_CANARY_SUMMARY total={len(cases)} "
        f"pass={len(cases) - len(failures)} fail={len(failures)} "
        f"model={GROQ_120B} checked_at={datetime.now(timezone.utc).isoformat()}"
    )
    if failures:
        for failure in failures:
            print("TEMPORAL_CANARY_FAILURE " + failure)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
