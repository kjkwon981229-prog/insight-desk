from __future__ import annotations

"""Qualification-only Gemini 2.5 Pro client for Event Understanding V4.

This candidate reuses only the already-isolated Gemini Interactions transport contract from the
Gemini 3.5 qualification client. It does not reuse or alter the production Gemini verification
failover owner, is not exported from ``insight_desk.providers``, and is not production-wired.
"""

from dataclasses import dataclass

from .gemini35 import Gemini35FlashStructuredClient
from .transport import JsonHttpTransport


GEMINI_25_PRO = "gemini-2.5-pro"


@dataclass(slots=True)
class Gemini25ProStructuredClient(Gemini35FlashStructuredClient):
    model_id: str = GEMINI_25_PRO
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GEMINI_25_PRO:
            raise ValueError("Gemini Event Understanding candidate is frozen to gemini-2.5-pro")
        if self.transport is None:
            self.transport = JsonHttpTransport()
