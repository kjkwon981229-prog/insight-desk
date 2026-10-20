from __future__ import annotations

import unittest

from insight_desk.core.relevance import (
    RelevanceReason,
    RelevanceVerdict,
    relevance_from_literal_match,
)

MARKET_TITLE = "뉴욕증시, 반도체·AI주 반등 속 혼조 마감...나스닥 1.11%↑"


class AiTechMarketOverviewTests(unittest.TestCase):
    def test_market_overview_is_not_ai_tech(self):
        decision = relevance_from_literal_match(topic_id="ai_tech", matched=True, title=MARKET_TITLE)
        self.assertIs(decision.verdict, RelevanceVerdict.IRRELEVANT)
        self.assertIn(RelevanceReason.MARKET_OVERVIEW_EXCLUDED, decision.reasons)

    def test_economy_topic_is_untouched(self):
        decision = relevance_from_literal_match(topic_id="economy", matched=True, title=MARKET_TITLE)
        self.assertIs(decision.verdict, RelevanceVerdict.RELEVANT)

    def test_product_article_stays_ai_tech(self):
        decision = relevance_from_literal_match(
            topic_id="ai_tech", matched=True, title="딥브레인AI, 15억 원 투입해 AI 비디오 에이전트 개발"
        )
        self.assertIs(decision.verdict, RelevanceVerdict.RELEVANT)


if __name__ == "__main__":
    unittest.main()
