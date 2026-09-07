from pathlib import Path
import unittest

from insight_desk.core import RelevanceVerdict
from insight_desk.production_relevance_v2 import ConfiguredLiteralRelevanceOwner
from scripts.phase11_daily_production_core import load_topics, topic_relevant


class CanonicalConditionalBindingTests(unittest.TestCase):
    def test_conditional_scope_is_proved_by_the_visible_proposition(self):
        topics = {t.topic_id: t for t in load_topics(Path("config/topics.json"))}
        owner = ConfiguredLiteralRelevanceOwner(topic_relevant)
        cases = (
            ("kbo_hanwha", "롯데 자이언츠가 투수를 엔트리에서 말소했다.", False),
            ("kbo_hanwha", "한화 이글스가 투수를 엔트리에서 말소했다.", True),
            ("psat_recruitment", "삼성전자가 신입사원 채용 일정을 발표했다.", False),
            ("psat_recruitment", "인사혁신처가 국가공무원 채용 일정을 발표했다.", True),
            ("kpop", "그룹 튜넥스가 신곡 퍼포먼스 비디오를 공개했다.", True),
        )
        for key, proposition, included in cases:
            with self.subTest(proposition=proposition):
                decision = owner.decide_canonical_proposition(
                    proposition=proposition, canonical_topic=key, topic=topics[key])
                self.assertEqual(decision.verdict == RelevanceVerdict.RELEVANT, included)


if __name__ == "__main__":
    unittest.main()
