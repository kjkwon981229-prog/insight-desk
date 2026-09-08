from __future__ import annotations

import unittest

from scripts.validate_feed_artifact import validate_html


_SOURCE_URL = "https://example.com/news/1"


def _audit() -> dict[str, object]:
    return {
        "publication_contract_version": 2,
        "canonical_contract": {"validated": True},
        "runtime_authority": {
            "story_admission_semantic_gate": False,
            "visible_identity_semantic_gate": False,
        },
        "rendered_sources": [
            {
                "event_id": "event:1",
                "source_group_key": "source-group:1",
                "content_sha256": "a" * 64,
                "source_url": _SOURCE_URL,
            }
        ],
    }


def _html(*, marker: str | None, include_summary: bool) -> str:
    marker_attr = f' data-summary-elision="{marker}"' if marker is not None else ""
    summary = '<p class="story-summary">한화가 홈 경기에서 승리했다.</p>' if include_summary else ""
    return (
        f'<article class="story-row" data-event-id="event:1"{marker_attr}>'
        '<span class="story-topic">한화 이글스</span>'
        '<h3>한화가 홈 경기에서 승리했다.</h3>'
        f'{summary}'
        f'<a class="story-source" href="{_SOURCE_URL}">원문 보기</a>'
        '</article>'
    )


class FeedSummaryElisionContractTests(unittest.TestCase):
    def test_v2_accepts_exact_headline_collision_elision_marker(self) -> None:
        report = validate_html(
            _html(marker="headline-collision", include_summary=False),
            source_audit=_audit(),
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["story_count"], 1)
        self.assertEqual(report["max_summary_chars"], len("한화가 홈 경기에서 승리했다."))

    def test_missing_summary_without_marker_remains_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, r"FEED_QUALITY_INCOMPLETE_STORY:1"):
            validate_html(_html(marker=None, include_summary=False), source_audit=_audit())

    def test_unknown_elision_marker_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, r"FEED_QUALITY_SUMMARY_ELISION_INVALID:1"):
            validate_html(_html(marker="unknown", include_summary=False), source_audit=_audit())

    def test_marker_and_visible_summary_cannot_coexist(self) -> None:
        with self.assertRaisesRegex(ValueError, r"FEED_QUALITY_SUMMARY_ELISION_CONFLICT:1"):
            validate_html(
                _html(marker="headline-collision", include_summary=True),
                source_audit=_audit(),
            )


if __name__ == "__main__":
    unittest.main()
