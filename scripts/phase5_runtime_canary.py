from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from insight_desk.acquisition import (
    AcquisitionPipeline,
    ArticleCandidate,
    PlaywrightHtmlRenderer,
    TrafilaturaExtractor,
    UrlLibHtmlFetcher,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "acquisition"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def fixture_server() -> Iterator[str]:
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(FIXTURES), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def make_candidate(url: str, *, candidate_id: str, title: str, topic: str) -> ArticleCandidate:
    return ArticleCandidate(
        candidate_id=candidate_id,
        url=url,
        search_title=title,
        source_name="127.0.0.1",
        published_at=datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc),
        topic_ids=(topic,),
        query="phase5 controlled runtime canary",
        retrieved_via="controlled_fixture",
    )


def assert_literals(text: str, literals: tuple[str, ...]) -> None:
    missing = [literal for literal in literals if literal not in text]
    if missing:
        raise AssertionError(f"protected literals missing after acquisition: {missing}")


def main() -> None:
    fetcher = UrlLibHtmlFetcher(timeout=10)
    extractor = TrafilaturaExtractor()
    renderer = PlaywrightHtmlRenderer(timeout_ms=15_000)

    with fixture_server() as base:
        static = AcquisitionPipeline(fetcher=fetcher, primary_extractor=extractor).acquire(
            make_candidate(
                f"{base}/static_article.html",
                candidate_id="canary-static",
                title="static search fallback",
                topic="ai_tech",
            )
        )
        assert not static.fallback_used
        assert static.extraction_method == "http+trafilatura"
        assert static.article.title == "SK하이닉스 9월 3일 신규 계획 발표"
        assert_literals(
            static.article.body,
            (
                "SK하이닉스",
                "9월 3일",
                "13.6%",
                "317억 달러",
                "1,050만 명",
                "“영업이익률은 13.6%”",
            ),
        )

        js = AcquisitionPipeline(
            fetcher=fetcher,
            primary_extractor=extractor,
            fallback_renderer=renderer,
        ).acquire(
            make_candidate(
                f"{base}/js_only.html",
                candidate_id="canary-js",
                title="JS 렌더링 기사 테스트",
                topic="kbo_hanwha",
            )
        )
        assert js.fallback_used
        assert js.extraction_method == "playwright+trafilatura"
        assert_literals(
            js.article.body,
            (
                "한화 이글스",
                "8월 24일",
                "오후 6시 30분",
                "“경기 시작 시각은 오후 6시 30분”",
            ),
        )

    report = {
        "status": "pass",
        "static": {
            "fallback_used": static.fallback_used,
            "method": static.extraction_method,
            "chars": static.quality.character_count,
            "title": static.article.title,
        },
        "js_only": {
            "fallback_used": js.fallback_used,
            "method": js.extraction_method,
            "chars": js.quality.character_count,
            "title": js.article.title,
        },
    }
    print("PHASE5_RUNTIME_CANARY_PASS")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
