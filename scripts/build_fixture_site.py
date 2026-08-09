from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insight_desk.domain.models import KeywordGroup  # noqa: E402
from insight_desk.run import execute  # noqa: E402


class FixtureClient:
    def __init__(self, root: Path) -> None:
        self.news = json.loads((root / "fixtures/news.json").read_text(encoding="utf-8"))
        self.trend = json.loads((root / "fixtures/trend.json").read_text(encoding="utf-8"))

    def search_news(self, query: str, *, display: int = 100, start: int = 1) -> dict[str, object]:
        return self.news.get(query, {"items": []})

    def search_trend(self, groups: list[KeywordGroup], *, start_date, end_date, time_unit="date"):
        return "fixture-batch", self.trend


def main() -> int:
    output = ROOT / "build/fixture-site"
    state = execute(
        config_path=ROOT / "config/topics.json",
        output_dir=output,
        state_path=ROOT / "build/fixture-run-state.json",
        cache_path=ROOT / "build/fixture-cache.json",
        client=FixtureClient(ROOT),
        source_mode="fixture",
    )
    print(state.status.value, state.publish)
    return 0 if state.publish else 1


if __name__ == "__main__":
    raise SystemExit(main())
