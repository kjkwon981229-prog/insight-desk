from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlparse

from insight_desk.feed_quality import VisibleStoryIssue
from insight_desk.story_admission import StoryAdmissionStage, evaluate_story_admission


MAX_HEADLINE_CHARS = 120
MAX_SUMMARY_CHARS = 420
PSAT_TOPIC = "PSAT·공채 일정"
PSAT_FORBIDDEN = (
    "Preparatory Student Academic",
    "PSAT 아카데미",
    "NCAA",
)
_URL_DATE_RE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])")
_FQ_STALE_SPORTS = "FEED_QUALITY_STALE_SPORTS_RETROSPECTIVE"


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    value = dict(attrs).get("class") or ""
    return set(value.split())


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def _stale_source_url(value: str) -> bool:
    parsed = urlparse(value)
    haystack = f"{parsed.path}?{parsed.query}"
    today = datetime.now(timezone.utc).date()
    for match in _URL_DATE_RE.finditer(haystack):
        try:
            candidate = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        if (today - candidate).days > 3:
            return True
    return False


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
                "source_url": "",
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
        elif tag == "a" and "story-source" in classes:
            self._story["source_url"] = attributes.get("href") or ""

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
) -> tuple[int, int, int]:
    rendered_sources = source_audit.get("rendered_sources")
    if not isinstance(rendered_sources, list):
        raise ValueError("FEED_QUALITY_SOURCE_AUDIT_MISSING")
    html_event_ids = [story["event_id"].strip() for story in stories]
    audit_event_ids: list[str] = []
    audit_source_urls: list[str] = []
    seen_source_groups: set[str] = set()
    seen_content: set[str] = set()
    invalid_source_url_indices: list[int] = []
    stale_source_url_indices: list[int] = []
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
        if not event_id or not source_group_key or not content_sha256:
            raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{index}")
        if not source_url_valid:
            invalid_source_url_indices.append(index)
        elif _stale_source_url(source_url):
            stale_source_url_indices.append(index)
        audit_event_ids.append(event_id)
        audit_source_urls.append(source_url)
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
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SOURCE_CONTENT:{duplicate_source_content}")
    if invalid_source_url_indices:
        raise ValueError(f"FEED_QUALITY_SOURCE_AUDIT_INVALID:{invalid_source_url_indices[0]}")
    if stale_source_url_indices:
        raise ValueError(f"FEED_QUALITY_STALE_SOURCE_URL:{stale_source_url_indices[0]}")
    for index, (story, source_url) in enumerate(
        zip(stories, audit_source_urls, strict=True), start=1
    ):
        visible_source_url = story.get("source_url", "").strip()
        if not visible_source_url:
            raise ValueError(f"FEED_QUALITY_SOURCE_LINK_MISSING:{index}")
        if visible_source_url != source_url:
            raise ValueError(f"FEED_QUALITY_SOURCE_LINK_MISMATCH:{index}")
    return duplicate_sources, duplicate_source_content, len(stale_source_url_indices)


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
    context_dependent_headlines = 0
    context_dependent_summaries = 0
    visible_metadata_issues = 0
    non_event_analytical_summaries = 0
    conditional_analytical_summaries = 0
    malformed_visible_texts = 0
    mixed_event_summaries = 0
    stale_dated_contexts = 0
    stale_sports_retrospectives = 0
    topic_binding_violations = 0
    max_headline = 0
    max_summary = 0
    psat_forbidden_hits: list[str] = []

    issue_values = {item.value for item in VisibleStoryIssue}

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

        decision = evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
        )
        codes = set(decision.compatibility_codes)
        topic_violation = VisibleStoryIssue.TOPIC_BINDING.value in codes
        if VisibleStoryIssue.HEADLINE_SUMMARY_COLLISION.value in codes:
            headline_summary_collisions += 1
        if (
            VisibleStoryIssue.CONTEXT_DEPENDENT_HEADLINE.value in codes
            and not topic_violation
        ):
            context_dependent_headlines += 1
        if VisibleStoryIssue.CONTEXT_DEPENDENT_SUMMARY.value in codes:
            context_dependent_summaries += 1
        if VisibleStoryIssue.VISIBLE_METADATA.value in codes:
            visible_metadata_issues += 1
        if VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY.value in codes:
            non_event_analytical_summaries += 1
        if VisibleStoryIssue.CONDITIONAL_ANALYTICAL_SUMMARY.value in codes:
            conditional_analytical_summaries += 1
        if VisibleStoryIssue.MALFORMED_VISIBLE_TEXT.value in codes:
            malformed_visible_texts += 1
        if VisibleStoryIssue.MIXED_EVENT_SUMMARY.value in codes:
            mixed_event_summaries += 1
        if _FQ_STALE_SPORTS in codes:
            stale_sports_retrospectives += 1
        elif VisibleStoryIssue.STALE_DATED_CONTEXT.value in codes:
            stale_dated_contexts += 1
        if topic_violation:
            topic_binding_violations += 1

        headline_key = _normalize(headline)
        summary_key = _normalize(summary)
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

        # Guard against a shared decision rejection that lacks a legacy public
        # FEED_QUALITY code. Production must fail closed rather than silently pass.
        if not decision.accepted and not (codes & issue_values) and _FQ_STALE_SPORTS not in codes:
            context_dependent_summaries += 1

    if headline_summary_collisions:
        raise ValueError(
            f"FEED_QUALITY_HEADLINE_SUMMARY_COLLISION:{headline_summary_collisions}"
        )
    if context_dependent_headlines:
        raise ValueError(
            f"FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE:{context_dependent_headlines}"
        )
    if context_dependent_summaries:
        raise ValueError(
            f"FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY:{context_dependent_summaries}"
        )
    if visible_metadata_issues:
        raise ValueError(f"FEED_QUALITY_VISIBLE_METADATA:{visible_metadata_issues}")
    if non_event_analytical_summaries:
        raise ValueError(
            f"FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY:{non_event_analytical_summaries}"
        )
    if conditional_analytical_summaries:
        raise ValueError(
            f"FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY:{conditional_analytical_summaries}"
        )
    if malformed_visible_texts:
        raise ValueError(f"FEED_QUALITY_MALFORMED_VISIBLE_TEXT:{malformed_visible_texts}")
    if mixed_event_summaries:
        raise ValueError(f"FEED_QUALITY_MIXED_EVENT_SUMMARY:{mixed_event_summaries}")
    if stale_sports_retrospectives:
        raise ValueError(
            f"FEED_QUALITY_STALE_SPORTS_RETROSPECTIVE:{stale_sports_retrospectives}"
        )
    if stale_dated_contexts:
        raise ValueError(f"FEED_QUALITY_STALE_DATED_CONTEXT:{stale_dated_contexts}")
    if topic_binding_violations:
        raise ValueError(f"FEED_QUALITY_TOPIC_BINDING:{topic_binding_violations}")
    if duplicate_headlines:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_HEADLINE:{duplicate_headlines}")
    if duplicate_summaries:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_SUMMARY:{duplicate_summaries}")
    if duplicate_content:
        raise ValueError(f"FEED_QUALITY_DUPLICATE_CONTENT:{duplicate_content}")
    if psat_forbidden_hits:
        raise ValueError(
            "FEED_QUALITY_PSAT_FALSE_POSITIVE:"
            + ",".join(sorted(set(psat_forbidden_hits)))
        )

    duplicate_sources = 0
    duplicate_source_content = 0
    stale_source_urls = 0
    if source_audit is not None:
        duplicate_sources, duplicate_source_content, stale_source_urls = _validate_source_audit(
            stories, source_audit
        )

    return {
        "status": "PASS",
        "story_count": len(stories),
        "max_headline_chars": max_headline,
        "max_summary_chars": max_summary,
        "headline_summary_collisions": headline_summary_collisions,
        "context_dependent_headlines": context_dependent_headlines,
        "context_dependent_summaries": context_dependent_summaries,
        "visible_metadata_issues": visible_metadata_issues,
        "non_event_analytical_summaries": non_event_analytical_summaries,
        "conditional_analytical_summaries": conditional_analytical_summaries,
        "malformed_visible_texts": malformed_visible_texts,
        "mixed_event_summaries": mixed_event_summaries,
        "stale_dated_contexts": stale_dated_contexts,
        "stale_sports_retrospectives": stale_sports_retrospectives,
        "topic_binding_violations": topic_binding_violations,
        "duplicate_headlines": duplicate_headlines,
        "duplicate_summaries": duplicate_summaries,
        "duplicate_content": duplicate_content,
        "duplicate_sources": duplicate_sources,
        "duplicate_source_content": duplicate_source_content,
        "stale_source_urls": stale_source_urls,
        "visible_source_links": sum(
            bool(story.get("source_url", "").strip()) for story in stories
        ),
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
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        "FEED_QUALITY_PASS "
        + " ".join(f"{key}={value}" for key, value in report.items() if key != "status")
    )


if __name__ == "__main__":
    main()
