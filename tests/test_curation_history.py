from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from insight_desk.curation.history import (
    HistoryError,
    SeenEntry,
    SeenHistory,
    load_history,
    make_entry,
    save_history,
)

KST = timezone(timedelta(hours=9))


class TestPrune(unittest.TestCase):
    def test_boundary_6d23h_kept(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        shown = now - timedelta(days=6, hours=23)
        entry = make_entry(topic_id="t1", title="테스트 기사", event_id="e1", shown_at=shown)
        h = SeenHistory(entries=(entry,))
        pruned = h.prune(now, days=7)
        self.assertEqual(len(pruned.entries), 1)

    def test_boundary_7d1h_removed(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        shown = now - timedelta(days=7, hours=1)
        entry = make_entry(topic_id="t1", title="테스트 기사", event_id="e1", shown_at=shown)
        h = SeenHistory(entries=(entry,))
        pruned = h.prune(now, days=7)
        self.assertEqual(len(pruned.entries), 0)

    def test_exactly_7d_removed(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        shown = now - timedelta(days=7)
        entry = make_entry(topic_id="t1", title="테스트 기사", event_id="e1", shown_at=shown)
        h = SeenHistory(entries=(entry,))
        pruned = h.prune(now, days=7)
        self.assertEqual(len(pruned.entries), 0)


class TestIsDuplicate(unittest.TestCase):
    def test_different_topic_not_duplicate(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        entry = make_entry(topic_id="t1", title="같은 제목 기사", event_id="e1", shown_at=now - timedelta(days=1))
        h = SeenHistory(entries=(entry,))
        self.assertFalse(h.is_duplicate(topic_id="t2", title="같은 제목 기사", now=now))


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        entry = make_entry(topic_id="t1", title="라운드트립 테스트", event_id="e1", shown_at=now)
        h = SeenHistory(entries=(entry,))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            save_history(path, h, now)
            loaded = load_history(path, now + timedelta(minutes=1))
            self.assertEqual(len(loaded.entries), 1)
            self.assertEqual(loaded.entries[0].event_id, "e1")

    def test_corrupt_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            path.write_text("{bad json", encoding="utf-8")
            now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
            with self.assertRaises(HistoryError):
                load_history(path, now)

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nonexistent.json"
            now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
            h = load_history(path, now)
            self.assertEqual(len(h.entries), 0)

    def test_no_temp_file_left_on_failure(self):
        now = datetime(2025, 1, 10, 0, 0, tzinfo=KST)
        entry = make_entry(topic_id="t1", title="테스트", event_id="e1", shown_at=now)
        h = SeenHistory(entries=(entry,))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            save_history(path, h, now)
            files_before = set(Path(td).iterdir())
            loaded = load_history(path, now)
            files_after = set(Path(td).iterdir())
            temp_files = [f for f in files_after if f.suffix == ".tmp"]
            self.assertEqual(len(temp_files), 0)


if __name__ == "__main__":
    unittest.main()
