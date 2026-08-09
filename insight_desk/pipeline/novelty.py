from __future__ import annotations

import json
import re
from pathlib import Path

from ..domain.models import NewsItem
from .clustering import StoryCluster
from .editorial import effective_title

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
    numbers: list[str] = []
    dates: list[str] = []
    for item in cluster.items:
        text = f"{effective_title(item)} {item.metadata_description if item.metadata_description else item.summary}"
        numbers.extend(re.findall(r"\d[\d,.]*(?:\s?(?:조원|억원|만원|달러|원|%|명|건|배|개|곳|일|년|개월|위|점))?", text))
        dates.extend(re.findall(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)", text))
    return "|".join(_signature_parts(event_type, title, tuple(dict.fromkeys(numbers)), tuple(dict.fromkeys(dates))))


def _family(signature: str) -> tuple[str, ...]:
    parts = tuple(part for part in signature.split("|") if part)
    return parts[:4]


def load_previous_signatures(output_dir: Path) -> tuple[str, ...]:
    """Read only the previously published latest payload when available."""

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
