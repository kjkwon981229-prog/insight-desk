from __future__ import annotations

from dataset import build_cases
from providers import PROVIDERS, ProviderError, available


def main() -> None:
    spec = PROVIDERS["groq20"]
    if not available(spec):
        print("GROQ_DIAGNOSTIC_SKIPPED missing_credentials")
        return
    case = build_cases()[0]
    try:
        output = spec.call(case)
    except ProviderError as exc:
        print(f"GROQ_DIAGNOSTIC_ERROR case={case['id']} detail={str(exc)[:4000]}")
        raise SystemExit(2)
    print(f"GROQ_DIAGNOSTIC_OK case={case['id']} output={output!r}")


if __name__ == "__main__":
    main()
