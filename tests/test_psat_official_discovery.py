from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from insight_desk.acquisition import ArticleCandidate, MpmOfficialBoardDiscovery, default_news_discovery
from insight_desk.acquisition import discovery as discovery_module
from insight_desk.acquisition.discovery import AggregatedNewsDiscovery, BingNewsRssDiscovery


PRESS = "https://www.mpm.go.kr/mpm/comm/newsPress/newsPressRelease/"


class _Response:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.content


class _Board:
    def __init__(self, rows: list[tuple[str, str, str]]) -> None:
        self.calls = 0
        self.rows = rows

    def __call__(self, request, *, timeout):
        self.calls += 1
        assert request.full_url.startswith(PRESS)
        assert timeout > 0
        body = "<table><tbody>" + "".join(
            f'<tr><td>1234</td><td><a href="{url}">{title}</a></td>'
            f'<td>시험출제과</td><td>{day}</td></tr>'
            for title, url, day in self.rows
        ) + "</tbody></table>"
        return _Response(body.encode("utf-8"))


class PsatOfficialDiscoveryTests(unittest.TestCase):
    def test_installed_package_reads_live_checkout_configuration(self) -> None:
        with patch.object(discovery_module, "__file__", "/tmp/site-packages/insight_desk/acquisition/discovery.py"):
            routes = discovery_module._configured_mpm_routes()
        self.assertEqual([route.route_id for route in routes],
                         ["mpm_press_releases", "mpm_exam_notices"])

    def test_official_board_precedes_news_and_does_not_fetch_for_other_topics(self) -> None:
        routes = default_news_discovery(env={}).routes
        self.assertEqual([route.route_id for route in routes[:2]],
                         ["mpm_press_releases", "mpm_exam_notices"])
        self.assertTrue(isinstance(routes[-1].inner, BingNewsRssDiscovery))

        today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        board = _Board([
            ("내년부터 검정시험… 공직적격성평가 운영 방향 발표",
             "?boardId=bbs_0000000000000029&cntId=4318&mode=view", today),
        ])
        route = MpmOfficialBoardDiscovery(PRESS, "mpm_press_releases", opener=board)
        self.assertEqual(route.search("AI", topic_id="ai_tech"), ())
        self.assertEqual(board.calls, 0)
        candidates = route.search("PSAT", topic_id="psat_recruitment")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_name, "인사혁신처")
        self.assertEqual(candidates[0].retrieved_via, "mpm_press_releases")
        self.assertTrue(candidates[0].url.startswith(PRESS))
        route.search("국가공무원 채용", topic_id="psat_recruitment")
        self.assertEqual(board.calls, 2)  # two pages fetched once for all queries

    def test_stale_and_offsite_links_and_promotion_do_not_fill_budget(self) -> None:
        today = datetime.now(timezone(timedelta(hours=9))).date()
        board = _Board([
            ("PSAT 시험 제도 개편", "https://ad.example/PSAT?cntId=12&mode=view", today.isoformat()),
            ("PSAT 학원 무료 설명회", "?cntId=88&mode=view", today.isoformat()),
            ("2026년 공직적격성평가 안내", "?cntId=9&mode=view",
             (today - timedelta(days=10)).isoformat()),
            ("PSAT 시행계획 세부 공고", "?cntId=91&mode=view", today.isoformat()),
        ])
        route = MpmOfficialBoardDiscovery(PRESS, "mpm_press_releases", opener=board)
        candidates = route.search("PSAT", topic_id="psat_recruitment")
        self.assertEqual([candidate.search_title for candidate in candidates],
                         ["PSAT 학원 무료 설명회", "PSAT 시행계획 세부 공고"])
        # The board merely nominates titles; source/event relevance must reject a promotion.
        self.assertEqual(candidates[0].source_name, "인사혁신처")

    def test_official_failure_keeps_independent_news_route_available(self) -> None:
        def broken(_request, *, timeout):
            raise TimeoutError("board unavailable")

        official = MpmOfficialBoardDiscovery(PRESS, "mpm_press_releases", opener=broken)

        class News:
            route_id = "news"

            def search(self, query, *, topic_id, limit=10):
                del limit
                return (ArticleCandidate(
                    candidate_id="news-fallback", url="https://news.example/psat",
                    search_title="PSAT 공고", source_name="news.example",
                    published_at=datetime.now(timezone.utc), topic_ids=(topic_id,),
                    query=query, retrieved_via="news",
                ),)

        discovery = AggregatedNewsDiscovery((official, News()))
        self.assertEqual(discovery.search("PSAT", topic_id="psat_recruitment")[0].candidate_id,
                         "news-fallback")
        self.assertEqual(discovery.route_stats["mpm_press_releases"]["errors"], 1)
        self.assertEqual(discovery.route_stats["news"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
