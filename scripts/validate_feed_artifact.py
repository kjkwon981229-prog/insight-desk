from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


MAX_HEADLINE_CHARS = 120
MAX_SUMMARY_CHARS = 420
PSAT_TOPIC = "PSAT·공채 일정"
PSAT_FORBIDDEN = (
    "Preparatory Student Academic",
    "PSAT 아카데미",
    "NCAA",
)
_CONTEXT_DEPENDENT_SUMMARY_LEADS = ("여기에 ", "여기에,")
_NON_EVENT_ANALYTICAL_ENDINGS = ("설명하기 어렵다", "설명하기 힘들다")
_SENTENCE_TERMINALS = ".!?。！？"


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    value = dict(attrs).get("class") or ""
    return set(value.split())


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _sentence_identity(value: str) -> str:
    return _normalize(value).rstrip(_SENTENCE_TERMINALS).rstrip()


def _context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split())
    return any(normalized.startswith(cue) for cue in _CONTEXT_DEPENDENT_SUMMARY_LEADS)


def _non_event_analytical_summary(value: str) -> bool:
    normalized = " ".join(value.split()).rstrip(_SENTENCE_TERMINALS).rstrip()
    return normalized.endswith(_NON_EVENT_ANALYTICAL_ENDINGS)


class FeedParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stories: list[dict[str, str]] = []
        self._story: dict[str, str] | None = None
        self._field: str | None = None
        self._field_depth = 0
        self._story_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _classes(attrs)
        attributes = dict(attrs)
        if self._story is None and tag == "article" and "story-row" in classes:
            self._story = {
                "event_id": attributes.get("data-event-id") or "",
                "topic": "",
                "headline": "",
                "summary": "",
            }
            self._story_depth = 1
            return
        if self._story is None:
            return

        self._story_depth += 1
        if self._field is not None:
            self._field_depth += 1
            return
        if tag == "h3":
            self._field = "headline"
            self._field_depth = 1
        elif tag == "p" and "story-summary" in classes:
            self._field = "summary"
            self._field_depth = 1
        elif tag == "span" and "story-topic" in classes:
            self._field = "topic"
            self._field_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._story is None:
            return
        if self._field is not None:
            self._field_depth -= 1
            if self._field_depth == 0:
                self._field = None
        self._story_depth -= 1
        if self._story_depth == 0:
            self.stories.append(self._story)
            self._story = None
            self._field = None
            self._field_depth = 0

    def handle_data(self, data: str) -> None:
        if self._story is not None and self._field is not None:
            self._story[self._field] += data


def _validate_source_audit(
    stories: list[dict[str, str]],
    source_audit: dict[str, object],
) -> tuple[int, int]:
    rendered_sources = source_audit.get("rendered_sources")
    if not isinstance(rendered_sources, list):
        raise ValueError("FEED_QUALITY_SOURCE_AUDIT_MISSING")

    html_event_ids = [story["event_id"].strip() for story in stories]
    audit_event_ids: list[str] = []
    seen_source_groups: set[str] = set()
    seen_content: set[str] = set()
    duplicate_sources = 0
    duplicate_source_content = 0

    for index, item in enumerate(rendered_sources, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{index}")
        event_id = str(item.get("event_id") or "").strip()
        source_group_key = str(item.get("source_group_key") or "").strip()
        content_sha256 = str(item.get("content_sha256") or "").strip()
        source_url = str(item.get("source_url") or "").strip()
        parsed_source_url = urlparse(source_url)
        source_url_valid = (
            parsed_source_url.scheme in {"http", "https"}
            and bool(parsed_source_url.netloc)
            and parsed_source_url.username is None
            and parsed_source_url.password is None
        )
        if not event_id or not source_group_key or not content_sha256 or not source_url_valid:
            raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{index}")
        audit_event_ids.append(event_id)
        if source_group_key in seen_source_groups:
            duplicate_sources += 1
        else:
            seen_source_groups.add(source_group_key)
        if content_sha256 in seen_content:
            duplicate_source_content += 1
        else:
            seen_content.add(content_sha256)

    if html_event_ids != audit_event_ids:
        raise ValueError("FEED_QUALITY_SOURCE_AUDIT_EVENT_MISMATCH")
    if duplicate_sources:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SOURCE:{duplicate_sources}")
    if duplicate_source_content:
        raise ValueError(
            f"FEED_QUALITY_DUPLICATE_SOURCE_CONTENT:{duplicate_source_content}"
        )
    return duplicate_sources, duplicate_source_content


def validate_html(
    html: str,
    *,
    source_audit: dict[str, object] | None = None,
) -> dict[str, object]:
    parser = FeedParser()
    parser.feed(html)
    stories = parser.stories
    if not stories:
        raise ValueError("FEED_QUALITY_NO_STORIES")

    seen_headlines: set[str] = set()
    seen_summaries: set[str] = set()
    seen_content: set[tuple[str, str]] = set()
    duplicate_headlines = 0
    duplicate_summaries = 0
    duplicate_content = 0
    headline_summary_collisions = 0
    context_dependent_summaries = 0
    non_event_analytical_summaries = 0
    max_headline = 0
    max_summary = 0
    psat_forbidden_hits: list[str] = []

    for index, story in enumerate(stories, start=1):
        event_id = story["event_id"].strip()
        headline = story["headline"].strip()
        summary = story["summary"].strip()
        topic = story["topic"].strip()
        if not event_id or not headline or not summary:
            raise ValueError(f"FEED_QUALITY_INCOMPLETE_STORY:{index}")

        max_headline = max(max_headline, len(headline))
        max_summary = max(max_summary, len(summary))
        if len(headline) > MAX_HEADLINE_CHARS:
            raise ValueError(f"FEED_QUALITY_HEADLINE_TOO_LONG:{index}:{len(headline)}")
        if len(summary) > MAX_SUMMARY_CHARS:
            raise ValueError(f"FEED_QUALITY_SUMMARY_TOO_LONG:{index}:{len(summary)}")

        headline_key = _normalize(headline)
        summary_key = _normalize(summary)
        if _sentence_identity(headline) == _sentence_identity(summary):
            headline_summary_collisions += 1
        if _context_dependent_summary(summary):
            context_dependent_summaries += 1
        if _non_event_analytical_summary(summary):
            non_event_analytical_summaries += 1

        if headline_key in seen_headlines:
            duplicate_headlines += 1
        else:
            seen_headlines.add(headline_key)

        if summary_key in seen_summaries:
            duplicate_summaries += 1
        else:
            seen_summaries.add(summary_key)

        content_key = (headline_key, summary_key)
        if content_key in seen_content:
            duplicate_content += 1
        else:
            seen_content.add(content_key)

        if topic == PSAT_TOPIC:
            combined = f"{headline}\n{summary}".casefold()
            for forbidden in PSAT_FORBIDDEN:
                if forbidden.casefold() in combined:
                    psat_forbidden_hits.append(forbidden)

    if headline_summary_collisions:
        raise ValueError(
            f"FEED_QUALITY_HEADLINE_SUMMARY_COLLISION:{headline_summary_collisions}"
        )
    if context_dependent_summaries:
        raise ValueError(
            f"FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY:{context_dependent_summaries}"
        )
    if non_event_analytical_summaries:
        raise ValueError(
            f"FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY:{non_event_analytical_summaries}"
        )
    if duplicate_headlines:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_HEADLINE:{duplicate_headlines}")
    if duplicate_summaries:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SUMMARY:{duplicate_summaries}")
    if duplicate_content:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_CONTENT:{duplicate_content}")
    if psat_forbidden_hits:
        raise ValueError("FEED_QUALITY_PSAT_FALSE_POSITIVE:" + ",".join(sorted(set(psat_forbidden_hits))))

    duplicate_sources = 0
    duplicate_source_content = 0
    if source_audit is not None:
        duplicate_sources, duplicate_source_content = _validate_source_audit(
            stories,
            source_audit,
        )

    return {
        "status": "PASS",
        "story_count": len(stories),
        "max_headline_chars": max_headline,
        "max_summary_chars": max_summary,
        "headline_summary_collisions": headline_summary_collisions,
        "context_dependent_summaries": context_dependent_summaries,
        "non_event_analytical_summaries": non_event_analytical_summaries,
        "duplicate_headlines": duplicate_headlines,
        "duplicate_summaries": duplicate_summaries,
        "duplicate_content": duplicate_content,
        "duplicate_sources": duplicate_sources,
        "duplicate_source_content": duplicate_source_content,
        "psat_forbidden_hits": 0,
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    source_audit = None
    if args.audit is not None:
        source_audit = json.loads(args.audit.read_text(encoding="utf-8"))
        if not isinstance(source_audit, dict):
            raise ValueError("FEED_QUALITY_SOURCE_AUDIT_INVALID_ROOT")
    report = validate_html(html, source_audit=source_audit)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FEED_QUALITY_PASS " + " ".join(f"{key}={value}" for key, value in report.items() if key != "status"))


if __name__ == "__main__":
    main()
