from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from .text import content_words, jaccard


class HistoryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SeenEntry:
    argument_hash: str
    topic_id: str
    shown_at: datetime
    event_id: str
    title_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class SeenHistory:
    entries: tuple[SeenEntry, ...] = ()

    def prune(self, now: datetime, days: int = 7) -> SeenHistory:
        cutoff = now - timedelta(days=days)
        kept = tuple(e for e in self.entries if e.shown_at > cutoff)
        return SeenHistory(entries=kept)

    def is_duplicate(
        self,
        *,
        topic_id: str,
        title: str,
        now: datetime,
        days: int = 7,
        jaccard_threshold: float = 0.6,
    ) -> bool:
        pruned = self.prune(now, days)
        tokens = content_words(title)
        h = argument_hash(topic_id, title)
        for e in pruned.entries:
            if e.topic_id != topic_id:
                continue
            if e.argument_hash == h:
                return True
            if jaccard(tokens, e.title_tokens) >= jaccard_threshold:
                return True
        return False

    def add(self, entry: SeenEntry) -> SeenHistory:
        return SeenHistory(entries=self.entries + (entry,))


def argument_hash(topic_id: str, title: str) -> str:
    words = sorted(content_words(title))
    raw = topic_id + "\x00" + "\x00".join(words)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_entry(
    *, topic_id: str, title: str, event_id: str, shown_at: datetime
) -> SeenEntry:
    return SeenEntry(
        argument_hash=argument_hash(topic_id, title),
        topic_id=topic_id,
        shown_at=shown_at,
        event_id=event_id,
        title_tokens=content_words(title),
    )


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise HistoryError("datetime must be timezone-aware")
    return dt


def load_history(path: Path, now: datetime) -> SeenHistory:
    if not path.exists():
        return SeenHistory()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise HistoryError(str(exc)) from exc
    if not isinstance(data, dict):
        raise HistoryError("invalid schema")
    if data.get("schema_version") != 1:
        raise HistoryError("unsupported schema_version")
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise HistoryError("missing entries")
    entries: list[SeenEntry] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            raise HistoryError("invalid entry")
        required = {"argument_hash", "topic_id", "shown_at", "event_id", "title_tokens"}
        if not required.issubset(item.keys()):
            raise HistoryError("missing fields in entry")
        try:
            shown_at = _parse_dt(item["shown_at"])
            tokens = frozenset(item["title_tokens"])
        except Exception as exc:
            raise HistoryError(str(exc)) from exc
        entries.append(
            SeenEntry(
                argument_hash=item["argument_hash"],
                topic_id=item["topic_id"],
                shown_at=shown_at,
                event_id=item["event_id"],
                title_tokens=tokens,
            )
        )
    history = SeenHistory(entries=tuple(entries))
    return history.prune(now)


def save_history(path: Path, history: SeenHistory, now: datetime) -> None:
    pruned = history.prune(now)
    payload = {
        "schema_version": 1,
        "updated_at": now.isoformat(),
        "entries": [
            {
                "argument_hash": e.argument_hash,
                "topic_id": e.topic_id,
                "shown_at": e.shown_at.isoformat(),
                "event_id": e.event_id,
                "title_tokens": sorted(e.title_tokens),
            }
            for e in pruned.entries
        ],
    }
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
