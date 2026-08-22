from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from claim_cases import as_provider_cases
from providers import PROVIDERS, ProviderError, available


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    spec = PROVIDERS[args.provider]
    if not available(spec):
        raise SystemExit(f"CLAIM_VERIFY_SKIPPED provider={spec.id} reason=credentials_absent")

    rows = []
    errors = []
    passed = 0
    cases = as_provider_cases()

    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        try:
            prediction = spec.call(case)
            latency_ms = round((time.monotonic() - started) * 1000)
            expected = case["expected"]["entailed"]
            actual = prediction.get("entailed")
            ok = isinstance(actual, bool) and actual == expected
            passed += int(ok)
            rows.append(
                {
                    "id": case["id"],
                    "source_case": case["source_case"],
                    "expected": expected,
                    "actual": actual,
                    "pass": ok,
                    "latency_ms": latency_ms,
                }
            )
            print(
                f"CLAIM_VERIFY_CASE provider={spec.id} index={index}/{len(cases)} "
                f"case={case['id']} expected={str(expected).lower()} actual={str(actual).lower()} "
                f"pass={str(ok).lower()} latency_ms={latency_ms}"
            )
        except ProviderError as exc:
            latency_ms = round((time.monotonic() - started) * 1000)
            errors.append({"id": case["id"], "error": str(exc), "latency_ms": latency_ms})
            print(
                f"CLAIM_VERIFY_CASE provider={spec.id} index={index}/{len(cases)} "
                f"case={case['id']} status=error latency_ms={latency_ms}"
            )
        if index < len(cases) and spec.delay_seconds:
            time.sleep(spec.delay_seconds)

    report = {
        "provider": spec.id,
        "cases": len(cases),
        "responses": len(rows),
        "errors": len(errors),
        "passed": passed,
        "accuracy": round(passed / len(cases), 4),
        "rows": rows,
        "error_rows": errors,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"CLAIM_VERIFY_RESULT provider={spec.id} passed={passed}/{len(cases)} "
        f"responses={len(rows)}/{len(cases)} errors={len(errors)} accuracy={report['accuracy']}"
    )
    raise SystemExit(0 if len(rows) == len(cases) else 2)


if __name__ == "__main__":
    main()
