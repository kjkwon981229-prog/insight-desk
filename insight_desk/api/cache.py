from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class ResponseCache:
    """Small public-response cache; credentials are never stored."""

    def __init__(self, path: Path, ttl_seconds: int = 6 * 60 * 60) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, dict[str, Any]] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = loaded
            except (OSError, json.JSONDecodeError):
                self._data = {}

    @staticmethod
    def key(method: str, url: str, body: bytes | None) -> str:
        return hashlib.sha256((method + "\n" + url + "\n").encode() + (body or b"")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._data.get(key)
        if not isinstance(entry, dict):
            return None
        if time.time() - float(entry.get("fetched_at", 0)) > self.ttl_seconds:
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        self._data[key] = {"fetched_at": time.time(), "payload": payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(self._data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)
