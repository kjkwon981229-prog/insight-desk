from __future__ import annotations

"""Candidate-local V3 qualification lane for Hugging Face/Nscale Qwen3 235B 2507.

The provider binding is injected only for the duration of one qualification call. The canonical
V3 fixture, source reconstruction, adapter, scorer, lifecycle classification, report shape, and
exit codes remain owned by ``qualify_event_understanding_provider`` and are not duplicated here.
"""

import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Iterator

from insight_desk.providers.hf_qwen235b2507_nscale import (
    HF_QWEN3_235B_2507_NSCALE,
    HuggingFaceQwen235B2507NscaleStructuredClient,
)
from scripts import qualify_event_understanding_provider as canonical


CANDIDATE_PROVIDER = "hf_qwen235b2507_nscale"


@contextmanager
def registered_candidate_provider() -> Iterator[None]:
    """Temporarily bind only provider selection; preserve every canonical V3 semantic contract."""

    original_choices = canonical.PROVIDER_CHOICES
    original_model = canonical._provider_model
    original_configured = canonical._provider_configured
    original_client = canonical._provider_client

    def provider_model(provider: str) -> str:
        if provider == CANDIDATE_PROVIDER:
            return HF_QWEN3_235B_2507_NSCALE
        return original_model(provider)

    def provider_configured(provider: str) -> bool:
        if provider == CANDIDATE_PROVIDER:
            return HuggingFaceQwen235B2507NscaleStructuredClient.configured()
        return original_configured(provider)

    def provider_client(provider: str):
        if provider == CANDIDATE_PROVIDER:
            return (
                HuggingFaceQwen235B2507NscaleStructuredClient.from_env(),
                HF_QWEN3_235B_2507_NSCALE,
            )
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


def qualify(
    *,
    qualification_path: Path = canonical.DEFAULT_QUALIFICATION,
    scopes_path: Path = canonical.DEFAULT_SCOPES,
    report_path: Path = canonical.DEFAULT_REPORT,
) -> int:
    with registered_candidate_provider():
        return canonical.qualify(
            provider=CANDIDATE_PROVIDER,
            qualification_path=qualification_path,
            scopes_path=scopes_path,
            report_path=report_path,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", type=Path, default=canonical.DEFAULT_QUALIFICATION)
    parser.add_argument("--scopes", type=Path, default=canonical.DEFAULT_SCOPES)
    parser.add_argument("--report", type=Path, default=canonical.DEFAULT_REPORT)
    args = parser.parse_args()
    return qualify(
        qualification_path=args.qualification,
        scopes_path=args.scopes,
        report_path=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())
