from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dataset import build_cases
from providers import PROVIDERS, ProviderError, available


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--errors", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    spec = PROVIDERS[args.provider]
    if not available(spec):
        print(
            f"PROVIDER_SKIPPED provider={spec.id} reason=missing_credentials "
            f"required={','.join(spec.required_env)}"
        )
        return

    cases = build_cases()
    if args.limit is not None:
        cases = cases[: args.limit]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.errors:
        args.errors.parent.mkdir(parents=True, exist_ok=True)

    successes = 0
    errors: list[dict[str, str]] = []
    with args.output.open("w", encoding="utf-8") as stream:
        for index, case in enumerate(cases, start=1):
            started = time.monotonic()
            try:
                output = spec.call(case)
            except ProviderError as exc:
                errors.append({"case_id": case["id"], "error": str(exc)[:2000]})
                print(
                    f"PROVIDER_CASE provider={spec.id} index={index}/{len(cases)} "
                    f"case={case['id']} status=error"
                )
            else:
                elapsed_ms = round((time.monotonic() - started) * 1000)
                stream.write(
                    json.dumps(
                        {
                            "provider": spec.id,
                            "case_id": case["id"],
                            "output": output,
                            "latency_ms": elapsed_ms,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                stream.flush()
                successes += 1
                print(
                    f"PROVIDER_CASE provider={spec.id} index={index}/{len(cases)} "
                    f"case={case['id']} status=ok latency_ms={elapsed_ms}"
                )
            if index < len(cases) and spec.delay_seconds:
                time.sleep(spec.delay_seconds)

    if args.errors:
        args.errors.write_text(json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"PROVIDER_RUN_RESULT provider={spec.id} success={successes}/{len(cases)} "
        f"errors={len(errors)}"
    )
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
