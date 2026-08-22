from __future__ import annotations

import os

CHECKS = {
    "groq": ("GROQ_API_KEY",),
    "cloudflare": ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"),
    "gemini": ("GEMINI_API_KEY",),
}


def main() -> None:
    states = {
        provider: all(bool(os.environ.get(name, "")) for name in names)
        for provider, names in CHECKS.items()
    }
    print(
        "CREDENTIAL_AVAILABILITY "
        + " ".join(f"{provider}={str(present).lower()}" for provider, present in states.items())
    )


if __name__ == "__main__":
    main()
