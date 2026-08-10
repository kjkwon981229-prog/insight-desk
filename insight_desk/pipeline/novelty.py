from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from ..domain.models import NewsItem
from .clustering import StoryCluster
from .editorial import effective_title
from .semantics import canonical_event_signature, first_action

_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣·]{2,}")
_GENERIC = {"관련", "보도", "소식", "뉴스", "주요", "변화", "이슈", "확인"}


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token.casefold()
            for token in _TOKEN_RE.findall(value)
            if token.casefold() not in _GENERIC
        )
    )


def _signature_parts(event_type: str, title: str, numbers: object = (), dates: object = ()) -> tuple[str, ...]:
    number_values = numbers if isinstance(numbers, (list, tuple)) else ()
    date_values = dates if isinstance(dates, (list, tuple)) else ()
    return tuple(
        dict.fromkeys(
            (
                event_type or "OTHER",
                *_tokens(title)[:8],
                *(str(value) for value in number_values[:3]),
                *(str(value) for value in date_values[:2]),
            )
        )
    )


def current_signature(cluster: StoryCluster, event_type: str) -> str:
    representative = cluster.representative
    title = effective_title(representative)
    lead = representative.metadata_description or representative.summary
    return canonical_event_signature(
        event_type,
        title,
        lead=lead,
        action=first_action(title),
    )


def _family(signature: str) -> tuple[str, ...]:
    parts = tuple(part for part in signature.split("|") if part)
    return parts[:4]


def load_previous_signatures(output_dir: Path) -> tuple[str, ...]:
    """Read the private durable history before falling back to legacy output.

    The history file lives beside the Pages directory and is cached by the
    workflow; it is never copied into the public site.  This keeps novelty
    truthful without adding a database or exposing event signatures to users.
    """

    history_candidates = (
        output_dir.parent / "history" / "publication-signatures.json",
        output_dir / "history" / "publication-signatures.json",
    )
    for path in history_candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("signatures"), list):
            return tuple(str(value) for value in payload["signatures"] if isinstance(value, str) and value)

    candidates = (
        output_dir / "latest" / "data.json",
        output_dir / "data" / "latest.json",
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        signatures: list[str] = []
        for story in payload.get("stories", []):
            if not isinstance(story, dict):
                continue
            facts = story.get("facts", {}) if isinstance(story.get("facts", {}), dict) else {}
            stored_signature = str(facts.get("event_signature", "") or "").strip()
            if stored_signature:
                signatures.append(stored_signature)
                continue
            signatures.append(
                "|".join(
                    _signature_parts(
                        str(facts.get("event_type", "OTHER")),
                        str(story.get("title", "")),
                        facts.get("key_numbers", ()),
                        (facts.get("date", ""),) if facts.get("date") else (),
                    )
                )
            )
        return tuple(signature for signature in signatures if signature)
    return ()


def write_publication_signatures(path: Path, stories: tuple[object, ...], *, generated_at: str | datetime) -> None:
    """Persist the exact canonical signatures of the successfully rendered run."""

    signatures = []
    for story in stories:
        signature = str(
            getattr(story, "event_signature", "")
            or getattr(getattr(story, "facts", None), "event_signature", "")
            or ""
        ).strip()
        if signature and signature not in signatures:
            signatures.append(signature)
    timestamp = generated_at.isoformat(timespec="seconds") if isinstance(generated_at, datetime) else str(generated_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"version": 1, "generated_at": timestamp, "signatures": signatures}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def classify_novelty(signature: str, previous: tuple[str, ...]) -> str:
    if not previous:
        return "UNKNOWN_HISTORY"
    if signature in previous:
        return "UNCHANGED"
    family = _family(signature)
    for old in previous:
        old_family = _family(old)
        if family and old_family and family[0] == old_family[0]:
            overlap = len(set(family[1:]) & set(old_family[1:]))
            if overlap >= 1:
                return "UPDATE"
    return "NEW"
