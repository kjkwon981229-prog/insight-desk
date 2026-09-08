from __future__ import annotations

"""One-shot qualification wrapper for OpenRouter Qwen3-Next 80B under Event Understanding V5."""

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Iterator

from insight_desk.providers.openrouter_qwen3next80b import (
    OPENROUTER_QWEN3_NEXT_80B_FREE,
    OpenRouterQwen3Next80BStructuredClient,
)
from scripts import qualify_event_understanding_provider_v5 as canonical


CANDIDATE_PROVIDER = "openrouter_qwen3next80b"


@contextmanager
def registered_candidate_provider() -> Iterator[None]:
    original_choices = canonical.PROVIDER_CHOICES
    original_model = canonical._provider_model
    original_configured = canonical._provider_configured
    original_client = canonical._provider_client

    def provider_model(provider: str) -> str:
        if provider == CANDIDATE_PROVIDER:
            return OPENROUTER_QWEN3_NEXT_80B_FREE
        return original_model(provider)

    def provider_configured(provider: str) -> bool:
        if provider == CANDIDATE_PROVIDER:
            return OpenRouterQwen3Next80BStructuredClient.configured()
        return original_configured(provider)

    def provider_client(provider: str):
        if provider == CANDIDATE_PROVIDER:
            client = OpenRouterQwen3Next80BStructuredClient.from_env()
            return client, OPENROUTER_QWEN3_NEXT_80B_FREE
        return original_client(provider)

    canonical.PROVIDER_CHOICES = (*original_choices, CANDIDATE_PROVIDER)
    canonical._provider_model = provider_model
    canonical._provider_configured = provider_configured
    canonical._provider_client = provider_client
    try:
        yield
    finally:
        canonical.PROVIDER_CHOICES = original_choices
        canonical._provider_model = original_model
        canonical._provider_configured = original_configured
        canonical._provider_client = original_client


def qualify(*, report_path: Path) -> int:
    with registered_candidate_provider():
        return canonical.qualify(
            provider=CANDIDATE_PROVIDER,
            qualification_path=canonical.DEFAULT_QUALIFICATION,
            scopes_path=canonical.DEFAULT_SCOPES,
            report_path=report_path,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=canonical.DEFAULT_REPORT)
    args = parser.parse_args()
    return qualify(report_path=args.report)


if __name__ == "__main__":
    sys.exit(main())
