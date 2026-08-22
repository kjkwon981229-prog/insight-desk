from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks" / "bakeoff"))

from dataset import build_cases  # noqa: E402
from providers import PROVIDERS, ProviderError, available  # noqa: E402


TARGETS = {
    "run96-positive-groundbreaking",
    "run96-positive-solution-supply",
    "run96-positive-business-unit",
    "run96-tn-24",
}


def main() -> None:
    spec = PROVIDERS["groq120"]
    if not available(spec):
        print("GROQ120_FAILURE_PROBE_SKIPPED missing_credentials")
        return

    cases = [case for case in build_cases() if case["id"] in TARGETS]
    if {case["id"] for case in cases} != TARGETS:
        raise SystemExit("target case set mismatch")

    failures = 0
    for index, case in enumerate(cases, start=1):
        try:
            output = spec.call(case)
        except ProviderError as exc:
            failures += 1
            print(f"GROQ120_PROBE_ERROR case={case['id']} detail={str(exc)[:4000]}")
        else:
            print(f"GROQ120_PROBE_OK case={case['id']} output={output!r}")
        if index < len(cases):
            time.sleep(spec.delay_seconds)

    print(f"GROQ120_FAILURE_PROBE_RESULT cases={len(cases)} failures={failures}")


if __name__ == "__main__":
    main()
