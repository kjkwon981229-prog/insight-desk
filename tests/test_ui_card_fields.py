from __future__ import annotations

import unittest

from insight_desk.core import RenderMode
from insight_desk.ui import BriefingViewModel, StoryViewModel, render_briefing_html
from scripts.validate_feed_artifact import validate_html

LINES = ("매출 10% 증가함", "영업이익 확대 전망", "신제품 출시 예정")


def _story(**overrides) -> StoryViewModel:
    values = dict(
        index=1,
        event_id="event:a",
        headline="삼성전자 매출 10% 증가",
        summary="삼성전자 매출이 10% 증가했다.",
        render_mode=RenderMode.CANONICAL_RECOVERY,
        topic="AI·테크",
        source_url="https://example.com/a",
        selection_reason="관심 분야(AI·테크)와 직접 관련",
        core_lines=LINES,
    )
    values.update(overrides)
    return StoryViewModel(**values)


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
                "event_id": "event:a",
                "source_group_key": "source-group:a",
                "content_sha256": "a" * 64,
                "source_url": "https://example.com/a",
            }
        ],
    }


def _html(story: StoryViewModel) -> str:
    view = BriefingViewModel(briefing_id="daily-20261019T070000+0900", generated_label="2026. 10. 19 07:00", stories=(story,))
    return render_briefing_html(view)


class CardFieldRenderingTests(unittest.TestCase):
    def test_card_shows_reason_core_lines_and_buttons_without_the_summary_paragraph(self) -> None:
        page = _html(_story())
        self.assertIn('class="story-reason"', page)
        self.assertEqual(page.count("<li>"), 3)
        self.assertIn('data-summary-elision="core-lines"', page)
        self.assertNotIn('class="story-summary"', page)
        self.assertIn('data-action="good"', page)
        self.assertIn('data-action="bad"', page)
        self.assertIn('class="story-source"', page)

    def test_card_without_core_lines_keeps_the_verified_summary(self) -> None:
        page = _html(_story(core_lines=(), selection_reason="관심 분야(AI·테크)와 직접 관련"))
        self.assertIn('class="story-summary"', page)
        self.assertIn('class="story-reason"', page)
        self.assertNotIn("story-core", page)
        self.assertNotIn("data-summary-elision", page)

    def test_core_lines_must_be_exactly_three(self) -> None:
        with self.assertRaises(ValueError):
            _story(core_lines=LINES[:2])
        with self.assertRaises(ValueError):
            _story(core_lines=("가나다라", "", "마바사아"))

    def test_html_escapes_card_text(self) -> None:
        page = _html(_story(selection_reason="<b>x</b>", core_lines=("<i>가나다</i> 증가함", LINES[1], LINES[2])))
        self.assertNotIn("<b>x</b>", page)
        self.assertNotIn("<i>가나다</i>", page)


class ValidatorCardFieldTests(unittest.TestCase):
    def test_validator_accepts_core_lines_card(self) -> None:
        report = validate_html(_html(_story()), source_audit=_audit())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["story_count"], 1)

    def test_validator_accepts_degraded_card(self) -> None:
        report = validate_html(_html(_story(core_lines=())), source_audit=_audit())
        self.assertEqual(report["status"], "PASS")

    def test_validator_rejects_wrong_core_line_count(self) -> None:
        page = _html(_story()).replace("<li>신제품 출시 예정</li>", "")
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CORE_LINES_INVALID"):
            validate_html(page, source_audit=_audit())

    def test_validator_rejects_core_lines_without_elision_marker(self) -> None:
        page = _html(_story()).replace(' data-summary-elision="core-lines"', "")
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CORE_LINES_WITHOUT_ELISION|FEED_QUALITY_INCOMPLETE_STORY"):
            validate_html(page, source_audit=_audit())

    def test_validator_rejects_overlong_core_line(self) -> None:
        long_line = "가" * 81
        page = _html(_story(core_lines=(long_line, LINES[1], LINES[2])))
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CORE_LINE_TOO_LONG"):
            validate_html(page, source_audit=_audit())

    def test_validator_rejects_a_card_with_only_one_action_button(self) -> None:
        page = _html(_story())
        start = page.index('<button type="button" class="btn-bad"')
        end = page.index("</button>", start) + len("</button>")
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_ACTION_BUTTONS_INCOMPLETE"):
            validate_html(page[:start] + page[end:], source_audit=_audit())


if __name__ == "__main__":
    unittest.main()
