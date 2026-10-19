from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from insight_desk.curation.config import CurationConfig
from insight_desk.curation.scoring import score_article

KST = timezone(timedelta(hours=9))


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2025, 6, 15, 12, 0, tzinfo=KST)
        self.cfg = CurationConfig()

    def test_korean_economy_high_score(self):
        title = "한국 수출 역대 최초 600억 달러 돌파, 이번 주 발표 예정"
        body = (
            "산업통상자원부에 따르면 이번 주 한국 수출액이 사상 최초로 600억 달러를 넘어섰다. "
            "전년 대비 15% 증가했으며 반도체 수출은 30% 상승했다. "
            "전문가 분석에 따르면 이는 글로벌 수요 회복이 원인이다. "
            "향후 전망도 긍정적이다. 5월 무역수지 흑자는 50억 원 규모였다."
        )
        anchors = ["수출", "반도체", "무역수지", "산업통상자원부", "글로벌"]
        res = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=anchors, published_at=self.now - timedelta(hours=2),
            now=self.now, cfg=self.cfg,
        )
        self.assertGreaterEqual(res.total, 7.0)
        self.assertTrue(res.passed)

    def test_plain_article_below_7(self):
        title = "오늘 날씨 좋습니다"
        body = "하늘이 맑고 바람이 불어 산책하기 좋은 하루입니다. " * 20
        res = score_article(
            title=title, body=body, topic_id="weather",
            intent_anchors=[], published_at=None,
            now=self.now, cfg=self.cfg,
        )
        self.assertLess(res.total, 7.0)

    def test_psat_topic_can_reach_7(self):
        title = "2025년 PSAT 접수 마감 이번 주 일정 공고 발표"
        body = (
            "인사혁신처가 2025년 PSAT 원서 접수를 이번 주까지 진행한다고 공고했다. "
            "응시자는 5000명 규모이며 합격률은 30% 수준이다. "
            "시험 일정은 7월 1일로 예정되어 있으며 신청 방법은 홈페이지를 참고하면 된다. "
            "전문가 해석에 따르면 경쟁률이 역대 최고 수준이다."
        )
        anchors = ["PSAT", "접수", "마감", "인사혁신처", "시험"]
        res = score_article(
            title=title, body=body, topic_id="psat_recruitment",
            intent_anchors=anchors, published_at=self.now - timedelta(hours=5),
            now=self.now, cfg=self.cfg,
        )
        self.assertGreaterEqual(res.total, 7.0)

    def test_english_baseball_analysis(self):
        title = "All-Time Record: Ohtani Hits 30th Home Run, Analysis of His First MVP Season"
        body = (
            "Shohei Ohtani hit his 30th home run this week, setting an all-time record for Japanese players. "
            "According to sabermetrics analysis, his WAR is 5.2 versus last year's 4.1. "
            "He has 80 RBIs in 90 games. The background of his success is his training regimen. "
            "Experts say this is the first time a player achieved this milestone so early."
        )
        anchors = ["ohtani", "home run", "WAR", "sabermetrics", "MVP"]
        res = score_article(
            title=title, body=body, topic_id="baseball_sabermetrics",
            intent_anchors=anchors, published_at=self.now - timedelta(hours=10),
            now=self.now, cfg=self.cfg,
        )
        self.assertGreaterEqual(res.total, 7.0)

    def test_feedback_clamp(self):
        title = "테스트 기사"
        body = "본문 내용 " * 50
        res = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=[], published_at=None,
            now=self.now, cfg=self.cfg, feedback_adjust=10.0,
        )
        self.assertEqual(res.adjust, 1.0)
        res2 = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=[], published_at=None,
            now=self.now, cfg=self.cfg, feedback_adjust=-10.0,
        )
        self.assertEqual(res2.adjust, -2.0)

    def test_top_question_tiebreak(self):
        title = "테스트"
        body = "본문 " * 100
        res = score_article(
            title=title, body=body, topic_id="unknown_topic",
            intent_anchors=[], published_at=None,
            now=self.now, cfg=self.cfg,
        )
        if res.q1 == res.q2 == res.q3:
            self.assertEqual(res.top_question, "q1")

    def test_date_within_7_days(self):
        title = "행사 안내"
        body = "이번 행사는 6월 20일에 개최됩니다. " * 20
        res = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=[], published_at=None,
            now=self.now, cfg=self.cfg,
        )
        self.assertGreaterEqual(res.q3, 1)

    def test_year_end_wraparound(self):
        now = datetime(2025, 12, 28, 12, 0, tzinfo=KST)
        title = "연말 행사"
        body = "새해 행사가 1월 3일에 열립니다. " * 20
        res = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=[], published_at=None,
            now=now, cfg=self.cfg,
        )
        self.assertGreaterEqual(res.q3, 1)

    def test_timezone_awareness(self):
        utc_now = datetime(2025, 6, 15, 3, 0, tzinfo=timezone.utc)
        title = "시간대 테스트"
        body = "본문 " * 100
        res = score_article(
            title=title, body=body, topic_id="economy",
            intent_anchors=[], published_at=None,
            now=utc_now, cfg=self.cfg,
        )
        self.assertIsInstance(res.total, float)


if __name__ == "__main__":
    unittest.main()
