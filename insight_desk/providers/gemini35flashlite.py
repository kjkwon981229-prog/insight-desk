from __future__ import annotations

"""Qualification-only Gemini 3.5 Flash-Lite client for Event Understanding V4.

This candidate reuses only the already-isolated Gemini 3.5 qualification transport contract.
It does not reuse or alter the production Gemini 3.1 Flash-Lite verification-failover owner,
is not exported from ``insight_desk.providers``, and is not production-wired.
"""

from dataclasses import dataclass

from .gemini35 import Gemini35FlashStructuredClient
from .transport import JsonHttpTransport


GEMINI_35_FLASH_LITE = "gemini-3.5-flash-lite"


@dataclass(slots=True)
class Gemini35FlashLiteStructuredClient(Gemini35FlashStructuredClient):
    model_id: str = GEMINI_35_FLASH_LITE
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GEMINI_35_FLASH_LITE:
            raise ValueError(
                "Gemini Event Understanding candidate is frozen to gemini-3.5-flash-lite"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport()
