from __future__ import annotations

"""One-shot qualification wrapper for Mistral Medium 3.5 under Event Understanding V5.

The candidate is registered only inside this wrapper's context. Historical V3/V4 runners and the
canonical V5 runner remain provider-neutral outside that scope.
"""

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Iterator

from insight_desk.providers.mistral_medium35 import (
    MISTRAL_MEDIUM_35,
    MistralMedium35StructuredClient,
)
from scripts import qualify_event_understanding_provider_v5 as canonical


CANDIDATE_PROVIDER = "mistral_medium35"


@contextmanager
def registered_candidate_provider() -> Iterator[None]:
    original_choices = canonical.PROVIDER_CHOICES
    original_model = canonical._provider_model
    original_configured = canonical._provider_configured
    original_client = canonical._provider_client

    def provider_model(provider: str) -> str:
        if provider == CANDIDATE_PROVIDER:
            return MISTRAL_MEDIUM_35
        return original_model(provider)

    def provider_configured(provider: str) -> bool:
        if provider == CANDIDATE_PROVIDER:
            return MistralMedium35StructuredClient.configured()
        return original_configured(provider)

    def provider_client(provider: str):
        if provider == CANDIDATE_PROVIDER:
            client = MistralMedium35StructuredClient.from_env()
            return client, MISTRAL_MEDIUM_35
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
