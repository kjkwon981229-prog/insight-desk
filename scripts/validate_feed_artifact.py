from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path


MAX_HEADLINE_CHARS = 120
MAX_SUMMARY_CHARS = 420
PSAT_TOPIC = "PSAT·공채 일정"
PSAT_FORBIDDEN = (
    "Preparatory Student Academic",
    "PSAT 아카데미",
    "NCAA",
)


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    value = dict(attrs).get("class") or ""
    return set(value.split())


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


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


def validate_html(html: str) -> dict[str, object]:
    parser = FeedParser()
    parser.feed(html)
    stories = parser.stories
    if not stories:
        raise ValueError("FEED_QUALITY_NO_STORIES")

    seen_content: set[tuple[str, str]] = set()
    duplicate_content = 0
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

        content_key = (_normalize(headline), _normalize(summary))
        if content_key in seen_content:
            duplicate_content += 1
        else:
            seen_content.add(content_key)

        if topic == PSAT_TOPIC:
            combined = f"{headline}\n{summary}".casefold()
            for forbidden in PSAT_FORBIDDEN:
                if forbidden.casefold() in combined:
                    psat_forbidden_hits.append(forbidden)

    if duplicate_content:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_CONTENT:{duplicate_content}")
    if psat_forbidden_hits:
        raise ValueError("FEED_QUALITY_PSAT_FALSE_POSITIVE:" + ",".join(sorted(set(psat_forbidden_hits))))

    return {
        "status": "PASS",
        "story_count": len(stories),
        "max_headline_chars": max_headline,
        "max_summary_chars": max_summary,
        "duplicate_content": duplicate_content,
        "psat_forbidden_hits": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    report = validate_html(html)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FEED_QUALITY_PASS " + " ".join(f"{key}={value}" for key, value in report.items() if key != "status"))


if __name__ == "__main__":
    main()
