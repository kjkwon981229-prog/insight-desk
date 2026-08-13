from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_event
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.semantics import build_canonical_event, event_action_signal
from insight_desk.pipeline.synthesis import (
    _lineup_detail,
    editorial_text_issues,
    synthesize_cluster,
)
from scripts.validate_live_acceptance import validate as validate_live_acceptance

FIXTURE = Path(__file__).with_name("fixtures") / "run94_run95_semantic_replay.json"


def _topic(topic_id: str, query: str, anchors: tuple[str, ...], events: tuple[str, ...]) -> Topic:
    return Topic(
        topic_id,
        topic_id,
        True,
        False,
        60,
        (query,),
        candidate_budget=10,
        selection_cap=3,
        intent_anchors=anchors,
        event_terms=events,
    )


def _item(
    evidence_id: str,
    topic_id: str,
    query: str,
    title: str,
    lead: str,
    *,
    domain: str = "semantic.test",
    score: float = 88.0,
) -> NewsItem:
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=lead,
        original_url=f"https://{domain}/{evidence_id}",
        naver_url="",
        canonical_url=f"https://{domain}/{evidence_id}",
        published_at="2026-08-13T07:00:00+09:00",
        source_domain=domain,
        content_hash=evidence_id,
        score=score,
        metadata_title=title,
        metadata_description=lead,
        publisher=domain,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class Run94Run95SemanticConvergenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_run95_context_nouns_do_not_become_material_actions(self) -> None:
        topics = {
            "INDUSTRY_CHANGE": _topic("ai_tech", "AI", ("AI", "오라클"), ("전략", "투자")),
            "MARKET_MOVE": _topic("economy", "환율", ("환율", "원·달러"), ("환율", "상승")),
            "ROSTER_PERSONNEL": _topic("kbo_hanwha", "한화", ("한화", "야구"), ("선발",)),
        }
        for index, case in enumerate(self.payload["run95"]["context_noun_cases"], 1):
            event_type = case["event_type"]
            title = case["title"]
            self.assertEqual(event_action_signal(event_type, title), "", title)
            topic = topics[event_type]
            event = assess_event(
                StoryCluster(
                    topic.id,
                    (_item(f"context-{index}", topic.id, topic.news_queries[0], title, title),),
                ),
                topic,
            )
            self.assertEqual(event.event_type, event_type)
            self.assertFalse(event.passed, title)

        sports_topic = _topic("kbo_hanwha", "한화", ("한화", "야구"), ("기록", "승리"))
        sports = _item(
            "result-without-result",
            "kbo_hanwha",
            "한화",
            "한화 야구 투수의 시즌 기록 조명",
            "한화 투수의 시즌을 돌아본 분석 기사다.",
        )
        sports_event = assess_event(StoryCluster("kbo_hanwha", (sports,)), sports_topic)
        self.assertEqual(sports_event.event_type, "SPORTS_RESULT")
        self.assertFalse(sports_event.passed)
        self.assertFalse(sports_event.canonical_event.fact_complete)

    def test_typed_positive_event_matrix_survives(self) -> None:
        cases = (
            ("PRODUCT_RELEASE", "네오텔이 생성형 AI 요금제를 출시했다.", "출시"),
            ("MARKET_MOVE", "코스피가 4% 급등했다.", "급등"),
            ("AWARD_CHART", "가수 새봄이 음악 차트 14위에 올랐다.", "순위 기록"),
            ("INDUSTRY_CHANGE", "네오텔이 5000억원 규모 투자를 유치했다.", "유치"),
            ("ROSTER_PERSONNEL", "12일 선발투수로 문동주가 예고됐다.", "선발"),
            ("SPORTS_RESULT", "홍길동이 2홈런 3타점으로 승리했다.", "승리"),
        )
        for event_type, evidence, expected in cases:
            self.assertEqual(event_action_signal(event_type, evidence), expected, event_type)

    def test_run94_same_event_supporting_source_preserves_release_fact(self) -> None:
        topic = _topic("ai_tech", "AI", ("AI", "네오텔"), ("출시", "발표"))
        items = tuple(
            _item(
                record["id"],
                "ai_tech",
                "AI",
                record["title"],
                record["lead"],
                domain=record["domain"],
            )
            for record in self.payload["run94"]["multi_source_release"]
        )
        cluster = StoryCluster("ai_tech", items)
        result = select_clusters((cluster,), (topic,), limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.strong_rejected_candidates, 0)
        event = assess_event(cluster, topic)
        self.assertEqual(
            set(event.canonical_event.evidence_owner_ids), {item.evidence_id for item in items}
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="AI·테크",
            trend_metrics=(),
            canonical_event_override=event.canonical_event,
        )
        self.assertIn("네오텔", summary)
        self.assertIn("3만원", summary)
        self.assertIn("네오텔", facts.primary_focus_terms)

    def test_run94_policy_relation_survives_same_event_synthesis(self) -> None:
        items = tuple(
            _item(
                record["id"],
                "economy",
                "기준금리",
                record["title"],
                record["lead"],
                domain=record["domain"],
            )
            for record in self.payload["run94"]["multi_source_policy"]
        )
        event = build_canonical_event(
            "POLICY",
            items[0].metadata_title,
            lead=items[0].metadata_description,
            evidence_owner_ids=tuple(item.evidence_id for item in items),
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("economy", items),
            topic_name="경제",
            trend_metrics=(),
            canonical_event_override=event,
        )
        self.assertEqual(facts.subject, "한국은행 부총재")
        self.assertEqual(facts.action, "추가 인상 가능성 언급")
        self.assertIn("기준금리", summary)
        self.assertIn("추가", summary)
        self.assertIn("인상", summary)

    def test_run94_primary_focus_drift_is_blocked_but_real_trend_survives(self) -> None:
        topic = _topic("ai_tech", "게임업계", ("게임업계", "콘셉트"), ("확산", "공개"))
        mixed = self.payload["run94"]["mixed_focus"]
        mixed_item = _item("mixed", "ai_tech", "게임업계", mixed["title"], mixed["lead"])
        mixed_cluster = StoryCluster("ai_tech", (mixed_item,))
        mixed_event = assess_event(mixed_cluster, topic)
        self.assertEqual(mixed_event.event_type, "INDUSTRY_CHANGE")
        self.assertEqual(mixed_event.action, "확산")
        _, mixed_summary, _, _, _, _ = synthesize_cluster(
            mixed_cluster,
            topic_name="AI·테크",
            trend_metrics=(),
            canonical_event_override=mixed_event.canonical_event,
        )
        self.assertEqual(mixed_summary, "")
        mixed_selection = select_clusters((mixed_cluster,), (topic,), limit=10)
        self.assertEqual(mixed_selection.selected, ())
        self.assertEqual(mixed_selection.strong_rejected_candidates, 1)
        self.assertTrue(mixed_selection.filter_collapse)

        coherent = self.payload["run94"]["coherent_trend"]
        coherent_item = _item(
            "coherent", "ai_tech", "게임업계", coherent["title"], coherent["lead"]
        )
        coherent_cluster = StoryCluster("ai_tech", (coherent_item,))
        coherent_result = select_clusters((coherent_cluster,), (topic,), limit=10)
        self.assertEqual(len(coherent_result.selected), 1)
        coherent_event = assess_event(coherent_cluster, topic)
        _, summary, _, _, _, _ = synthesize_cluster(
            coherent_cluster,
            topic_name="AI·테크",
            trend_metrics=(),
            canonical_event_override=coherent_event.canonical_event,
        )
        self.assertIn("게임업계", summary)
        self.assertIn("흡혈귀 콘셉트", summary)
        self.assertNotIn("5000만", summary)

    def test_run95_particle_composition_is_bounded_and_general(self) -> None:
        self.assertEqual(_lineup_detail(self.payload["run95"]["malformed_lineup"]), ())
        self.assertEqual(
            _lineup_detail(self.payload["run95"]["explicit_lineup"]),
            ("한화 왕옌청", "두산 곽빈"),
        )
        malformed = (
            "이글스와과 베어스의가 예고됐다.",
            "선수을를 등록했다.",
            "구단은는 발표했다.",
            "타이거즈과와 라이온즈가 경기했다.",
        )
        for sentence in malformed:
            self.assertIn("MALFORMED_PARTICLE_STACK", editorial_text_issues(sentence), sentence)
        self.assertNotIn(
            "MALFORMED_PARTICLE_STACK", editorial_text_issues("레이디 가가가 신곡을 발표했다.")
        )

        title = "한화와 두산, 12일 선발투수 예고"
        lead = self.payload["run95"]["explicit_lineup"]
        item = _item("lineup", "kbo_hanwha", "한화", title, lead)
        event = build_canonical_event(
            "ROSTER_PERSONNEL",
            title,
            lead=lead,
            evidence_owner_ids=(item.evidence_id,),
        )
        _, summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("kbo_hanwha", (item,)),
            topic_name="KBO·한화",
            trend_metrics=(),
            canonical_event_override=event,
        )
        self.assertIn("한화 왕옌청과 두산 곽빈이", summary)
        self.assertNotIn("MALFORMED_PARTICLE_STACK", editorial_text_issues(summary))

    def test_run95_award_chart_action_is_a_predicate_not_context_noun(self) -> None:
        event = build_canonical_event(
            "AWARD_CHART",
            "새봄의 아리랑, 빌보드 앨범 차트 14위",
        )
        self.assertEqual(event.action, "순위 기록")
        self.assertTrue(event.fact_complete)
        item = _item(
            "chart",
            "kpop",
            "빌보드",
            "새봄의 아리랑, 빌보드 앨범 차트 14위",
            "새봄의 아리랑이 빌보드 앨범 차트 14위에 올랐다.",
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kpop", (item,)),
            topic_name="K-POP",
            trend_metrics=(),
            canonical_event_override=event,
        )
        self.assertEqual(facts.action, "순위 기록")
        self.assertIn("14위", summary)

    def test_run95_false_upstream_qualifications_are_removed_not_hidden(self) -> None:
        topics = (
            _topic("ai_tech", "AI", ("AI", "오라클"), ("전략", "투자")),
            _topic("economy", "환율", ("환율", "원·달러"), ("환율", "상승")),
            _topic("kbo_hanwha", "한화", ("한화", "야구"), ("기록", "승리")),
        )
        clusters = (
            StoryCluster(
                "ai_tech",
                (
                    _item(
                        "oracle",
                        "ai_tech",
                        "AI",
                        "데이터 중심으로 기술 모으는 오라클의 AI 전략",
                        "오라클의 기술 전략을 분석했다.",
                    ),
                ),
            ),
            StoryCluster(
                "economy",
                (
                    _item(
                        "level",
                        "economy",
                        "환율",
                        "원·달러 환율 1417.53원",
                        "원·달러 환율은 1417.53원이다.",
                    ),
                ),
            ),
            StoryCluster(
                "kbo_hanwha",
                (
                    _item(
                        "result",
                        "kbo_hanwha",
                        "한화",
                        "한화 야구 투수의 시즌 기록 조명",
                        "한화 투수의 시즌을 돌아본 분석 기사다.",
                    ),
                ),
            ),
        )
        result = select_clusters(clusters, topics, limit=10)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.strong_rejected_candidates, 0)
        for row in result.audit:
            self.assertNotIn("QUALIFIED", row["selection_reasons"])

    def test_old_run94_and_run95_artifacts_are_machine_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="insight-run94-run95-") as directory:
            path = Path(directory) / "live-acceptance.json"
            path.write_text(
                json.dumps(
                    {"selected_stories": [self.payload["run94"]["old_selected_story"]]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run94_errors = validate_live_acceptance(path)
            path.write_text(
                json.dumps(
                    {"selected_stories": self.payload["run95"]["old_selected_stories"]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run95_errors = validate_live_acceptance(path)

        self.assertTrue(any("primary event focus" in error for error in run94_errors))
        self.assertTrue(any("malformed deterministic Korean" in error for error in run95_errors))
        self.assertTrue(any("chart context noun" in error for error in run95_errors))
        self.assertTrue(any("starting-role noun" in error for error in run95_errors))


if __name__ == "__main__":
    unittest.main()
