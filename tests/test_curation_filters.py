from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from insight_desk.curation.config import CurationConfig
from insight_desk.curation.filters import apply_hard_filters
from insight_desk.curation.history import SeenHistory, make_entry

KST = timezone(timedelta(hours=9))


def _make_cfg(**kw):
    return CurationConfig(**kw)


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2025, 6, 15, 12, 0, tzinfo=KST)
        self.cfg = _make_cfg()
        self.body = "경제 지표가 개선되고 있습니다. 수출 물량이 증가하면서 제조업 생산도 늘어났습니다. " * 10

    def test_normal_column_passes(self):
        title = "경제 지표 개선 수출 물량 증가"
        res = apply_hard_filters(
            title=title, body=self.body, url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertFalse(res.rejected)

    def test_clickbait_phrase_only_passes_if_vocab_matches(self):
        title = "충격 경제 지표 알고 보니 대박"
        body = "경제 지표가 대폭 개선되었습니다. 수출 물량이 크게 증가했습니다. " * 20
        res = apply_hard_filters(
            title=title, body=body, url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertFalse(res.rejected, res.reason)

    def test_vocab_mismatch_only_no_clickbait_phrase_passes(self):
        title = "xyz abc def ghi"
        res = apply_hard_filters(
            title=title, body=self.body, url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertFalse(res.rejected)

    def test_both_clickbait_and_mismatch_rejected(self):
        title = "충격 알고 보니 xyz abc def ghi"
        res = apply_hard_filters(
            title=title, body=self.body, url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertTrue(res.rejected)
        self.assertEqual(res.reason, "clickbait")

    def test_ad_phrase_rejected(self):
        title = "최저가 상품 모음"
        res = apply_hard_filters(
            title=title, body=self.body, url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertTrue(res.rejected)
        self.assertEqual(res.reason, "ad_sponsored")

    def test_thin_content_rejected(self):
        res = apply_hard_filters(
            title="짧은 글", body="내용이 짧습니다.", url="https://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertTrue(res.rejected)
        self.assertEqual(res.reason, "thin_content")

    def test_no_url_rejected(self):
        res = apply_hard_filters(
            title="제목", body=self.body, url="ftp://example.com",
            topic_id="economy", negative_context=[], history=SeenHistory(),
            now=self.now, cfg=self.cfg,
        )
        self.assertTrue(res.rejected)
        self.assertEqual(res.reason, "no_source")

    def test_duplicate_7d_rejected(self):
        entry = make_entry(
            topic_id="economy", title="중복 기사 제목", event_id="e1",
            shown_at=self.now - timedelta(days=3),
        )
        history = SeenHistory(entries=(entry,))
        res = apply_hard_filters(
            title="중복 기사 제목", body=self.body, url="https://example.com",
            topic_id="economy", negative_context=[], history=history,
            now=self.now, cfg=self.cfg,
        )
        self.assertTrue(res.rejected)
        self.assertEqual(res.reason, "duplicate_7d")


if __name__ == "__main__":
    unittest.main()
