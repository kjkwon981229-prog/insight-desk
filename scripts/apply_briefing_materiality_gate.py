from __future__ import annotations

from pathlib import Path

EDITORIAL = Path("insight_desk/pipeline/editorial.py")
SELECTION = Path("insight_desk/pipeline/selection.py")
TEST = Path("tests/test_briefing_materiality.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


editorial = EDITORIAL.read_text(encoding="utf-8")
if "LOW_BRIEFING_MATERIALITY" in editorial:
    raise SystemExit("editorial.py already contains briefing materiality gate")

helper_anchor = '''def _is_routine_market_quote(title_text: str) -> bool:\n'''
helper_block = r'''_SOFT_BRIEFING_EVENT_TYPES = frozenset({"ANNOUNCEMENT", "SCHEDULED_EVENT", "ENTERTAINMENT_EVENT"})
_COMMON_LOW_INFORMATION_CONTENT_MARKERS = (
    "인터뷰", "화보", "포토", "티저", "로고 모션", "로고모션", "무드 필름", "무드필름",
    "콘셉트 포토", "콘셉트포토", "트랙리스트", "하이라이트 메들리", "스케줄러",
    "플레이리스트", "추천 플리", "챌린지", "커버", "퍼포먼스 영상", "퍼포먼스영상",
    "안무 영상", "안무영상", "숏폼", "비하인드", "브이로그", "셀카", "팬사인회",
    "캠페인", "게스트", "리액션", "반응 영상",
)
_KPOP_BRIEFING_MATERIAL_PATTERNS = (
    *_KPOP_MATERIAL_EVENT_PATTERNS,
    re.compile(r"(?:내달|다음\s?달|오는\s?\d{1,2}\s?월|\d{1,2}\s?월\s?\d{1,2}\s?일).{0,16}컴백"),
    re.compile(r"컴백.{0,16}(?:확정|예고|발표|예정|일정|날짜)"),
    re.compile(r"(?:확정|예고|발표|예정).{0,16}컴백"),
    re.compile(r"(?:콘서트|공연|월드투어).{0,20}(?:개최|개막|시작|확정|발표|예정|성료|마쳤다)"),
)
_AI_MATERIAL_OBJECT_MARKERS = (
    "인공지능", "AI", "모델", "에이전트", "GPU", "HBM", "반도체", "칩", "데이터센터",
    "클라우드", "플랫폼", "API", "서비스", "제품", "로봇", "로보틱스",
)
_AI_MATERIAL_ACTION_MARKERS = (
    "출시", "공개", "발표", "도입", "투자", "인수", "계약", "규제", "허가", "공급", "수주", "전환",
)
_ECONOMY_MATERIAL_MARKERS = (
    "한국은행", "기준금리", "금통위", "연준", "FOMC", "금융당국", "정부", "규제", "정책", "공시",
    "실적", "매출", "영업이익", "투자", "인수", "계약", "통계", "물가", "환율", "코스피", "증시",
)
_KBO_MATERIAL_MARKERS = (
    "트레이드", "영입", "등록", "말소", "부상", "징계", "규정", "계약", "방출", "은퇴",
    "중단", "취소", "재개", "순위", "홈런", "기록", "승리", "패배", "우승",
)
_PSAT_MATERIAL_MARKERS = (
    "원서접수", "시험일", "시험 일정", "공고", "합격자", "선발", "경쟁률", "시행", "개편", "제도", "채용", "공채",
)
_PSAT_LOW_INFORMATION_MARKERS = ("공부법", "합격수기", "강의", "교재", "학원", "팁", "전략", "인터뷰")
_ECONOMY_LOW_INFORMATION_MARKERS = ("전망", "추천", "인터뷰", "칼럼", "기고", "리포트", "가이드")


def _topic_family(topic: Topic) -> str:
    key = _compact(f"{topic.id} {topic.name}")
    if "kpop" in key or "케이팝" in key:
        return "kpop"
    if topic.id in {"ai", "ai_tech"} or key.startswith("ai") or "인공지능" in key:
        return "ai"
    if "economy" in key or "경제" in key or "투자" in key:
        return "economy"
    if "kbo" in key or "프로야구" in key or "한화이글스" in key:
        return "kbo"
    if "psat" in key or "공채" in key or "공직적격성평가" in key:
        return "psat"
    return "other"


def _briefing_materiality_passes(title_text: str, topic: Topic, event_type: str) -> bool:
    """Separate factual event validity from scarce daily-briefing value."""

    if event_type not in _SOFT_BRIEFING_EVENT_TYPES:
        return True

    # Reuse the already-locked semantic relation contract. Personnel changes,
    # partner/program selections, affiliation changes, and other complete
    # actor-action-object relations are material even when their broad event
    # family is ANNOUNCEMENT.
    if typed_event_relation(title_text) is not None:
        return True

    family = _topic_family(topic)
    low_information = any(_contains(title_text, marker) for marker in _COMMON_LOW_INFORMATION_CONTENT_MARKERS)

    if family == "kpop":
        if event_type == "ENTERTAINMENT_EVENT":
            return bool(
                any(_contains(title_text, marker) for marker in ("컴백", "콘서트", "공연", "월드투어", "앨범", "음원", "발매"))
                and not low_information
            )
        return bool(
            any(pattern.search(normalize_text(title_text)) for pattern in _KPOP_BRIEFING_MATERIAL_PATTERNS)
            and not low_information
        )

    if family == "ai":
        technical_object = any(_contains(title_text, marker) for marker in _AI_MATERIAL_OBJECT_MARKERS)
        material_action = any(_contains(title_text, marker) for marker in _AI_MATERIAL_ACTION_MARKERS)
        return bool(technical_object and material_action and not low_information)

    if family == "economy":
        low_information = low_information or any(_contains(title_text, marker) for marker in _ECONOMY_LOW_INFORMATION_MARKERS)
        return bool(any(_contains(title_text, marker) for marker in _ECONOMY_MATERIAL_MARKERS) and not low_information)

    if family == "kbo":
        return bool(any(_contains(title_text, marker) for marker in _KBO_MATERIAL_MARKERS) and not low_information)

    if family == "psat":
        low_information = low_information or any(_contains(title_text, marker) for marker in _PSAT_LOW_INFORMATION_MARKERS)
        return bool(any(_contains(title_text, marker) for marker in _PSAT_MATERIAL_MARKERS) and not low_information)

    return not low_information


'''
editorial = replace_once(editorial, helper_anchor, helper_block + helper_anchor, "helper insertion")

incidental_anchor = '''    incidental_ai = _is_incidental_ai_topic(\n        effective_title(representative),\n        topic,\n        event.event_type,\n        any(contains_action(effective_title(representative), term) for term in ("투자", "전략", "유치")),\n    )\n    truncated_title_without_lead = bool(\n'''
incidental_replacement = '''    incidental_ai = _is_incidental_ai_topic(\n        effective_title(representative),\n        topic,\n        event.event_type,\n        any(contains_action(effective_title(representative), term) for term in ("투자", "전략", "유치")),\n    )\n    briefing_material = _briefing_materiality_passes(\n        effective_title(representative), topic, event.event_type\n    )\n    truncated_title_without_lead = bool(\n'''
editorial = replace_once(editorial, incidental_anchor, incidental_replacement, "materiality evaluation")

reason_anchor = '''    if incidental_ai:\n        reasons.append("QUERY_OR_ACRONYM_ONLY_TOPIC_MATCH")\n    if evidence.conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}:\n'''
reason_replacement = '''    if incidental_ai:\n        reasons.append("QUERY_OR_ACRONYM_ONLY_TOPIC_MATCH")\n    if not briefing_material:\n        reasons.append("LOW_BRIEFING_MATERIALITY")\n    if evidence.conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}:\n'''
editorial = replace_once(editorial, reason_anchor, reason_replacement, "materiality reason")

reject_anchor = '''        or ownership_fact_gap\n        or incidental_ai\n        or evidence.conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}\n'''
reject_replacement = '''        or ownership_fact_gap\n        or incidental_ai\n        or not briefing_material\n        or evidence.conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}\n'''
editorial = replace_once(editorial, reject_anchor, reject_replacement, "materiality hard reject")
EDITORIAL.write_text(editorial, encoding="utf-8")

selection = SELECTION.read_text(encoding="utf-8")
if "LOW_BRIEFING_MATERIALITY" in selection:
    raise SystemExit("selection.py already contains briefing materiality diagnostic handling")

strong_anchor = '''    synthesis_vetoed_qualified = (\n'''
strong_replacement = '''    if any(\n        reason in assessment.reasons\n        for reason in ("LOW_VALUE_EVENT", "LOW_BRIEFING_MATERIALITY")\n    ):\n        return False\n\n    synthesis_vetoed_qualified = (\n'''
selection = replace_once(selection, strong_anchor, strong_replacement, "strong reject exemption")

predicate_anchor = '''        "RELEVANCE_FAILED",\n        "LOW_VALUE_EVENT",\n        "EVENT_ACTION_CONTRACT_FAILED",\n'''
predicate_replacement = '''        "RELEVANCE_FAILED",\n        "LOW_VALUE_EVENT",\n        "LOW_BRIEFING_MATERIALITY",\n        "EVENT_ACTION_CONTRACT_FAILED",\n'''
selection = replace_once(selection, predicate_anchor, predicate_replacement, "predicate reason")
SELECTION.write_text(selection, encoding="utf-8")

TEST.write_text(r'''from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster
from insight_desk.pipeline.selection import select_clusters


TOPICS, _ = load_topics(Path("config/topics.json"))
TOPIC = {topic.id: topic for topic in TOPICS}


def item(key: str, topic_id: str, query: str, title: str, summary: str) -> NewsItem:
    return NewsItem(
        evidence_id=key,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=summary,
        original_url=f"https://fixture.test/{key}",
        naver_url="",
        canonical_url=f"https://fixture.test/{key}",
        published_at="2026-08-21T10:00:00+09:00",
        source_domain="fixture.test",
        content_hash=key,
        score=90.0,
        metadata_title=title,
        metadata_description=summary,
        metadata_canonical_url=f"https://fixture.test/{key}",
        publisher="Fixture News",
        metadata_published_at="2026-08-21T10:00:00+09:00",
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class BriefingMaterialityTests(unittest.TestCase):
    def assessment(self, key: str, topic_id: str, query: str, title: str, summary: str):
        story = item(key, topic_id, query, title, summary)
        return assess_cluster(StoryCluster(topic_id, (story,)), TOPIC[topic_id], novelty="NEW")

    def test_soft_promo_and_lifestyle_content_is_not_briefing_material(self) -> None:
        cases = (
            ("kpop-photo", "kpop", "K-POP", "아이브, 새 앨범 콘셉트 포토 공개", "아이브가 8월 21일 새 앨범 콘셉트 포토를 공식 SNS에 공개했다."),
            ("kpop-playlist", "kpop", "K-POP", "BTS, 여름 플레이리스트 공개", "BTS 멤버가 8월 21일 직접 고른 여름 플레이리스트를 공개했다."),
            ("kpop-fansign", "kpop", "K-POP", "그룹 아이브, 팬사인회 성황", "그룹 아이브가 8월 21일 팬사인회를 진행했고 행사를 마쳤다."),
            ("ai-interview", "ai_tech", "OpenAI", "OpenAI CEO AI 인터뷰 영상 공개", "OpenAI CEO의 AI 산업 인터뷰 영상이 8월 21일 공개됐다."),
            ("kbo-schedule", "kbo_hanwha", "KBO", "KBO, 8월 21일 한화-LG 경기 일정 공개", "KBO가 8월 21일 한화와 LG의 정규시즌 경기 일정을 공개했다."),
            ("psat-study", "psat_recruitment", "PSAT", "PSAT 합격 공부법 영상 공개", "PSAT 합격 공부법을 설명하는 영상이 8월 21일 공개됐다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertFalse(assessment.qualified, title)
            self.assertIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)

    def test_material_soft_events_are_not_materiality_rejected(self) -> None:
        cases = (
            ("kpop-comeback", "kpop", "K-POP", "권은비, 9월 3일 컴백 확정", "권은비가 9월 3일 새 디지털 싱글을 발매하며 컴백한다고 발표했다."),
            ("kpop-next-month", "kpop", "K-POP", "권은비, 1년 4개월 공백 깨고 내달 컴백", "권은비가 내달 새 디지털 싱글을 발매하며 1년 4개월 만에 컴백한다."),
            ("ai-model", "ai_tech", "OpenAI", "OpenAI 새 AI 모델 공개", "OpenAI가 8월 21일 새 AI 모델을 공개하고 서비스 적용 계획을 발표했다."),
            ("ai-personnel", "ai_tech", "OpenAI", "OpenAI Replaces Chief Revenue Officer After Just 8 Months", "OpenAI replaced its chief revenue officer after eight months."),
            ("ai-selection", "ai_tech", "NVIDIA", "코팅솔루션포유, NVIDIA 협업 프로그램 선정", "코팅솔루션포유가 NVIDIA 협업 프로그램 참여사로 선정됐다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertNotIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)
            self.assertTrue(assessment.event.passed, (title, assessment.reasons))

    def test_strong_event_families_remain_eligible(self) -> None:
        cases = (
            ("economy-policy", "economy", "금융당국", "금융당국 레버리지 ETF 투자한도 100만원 규제 시행", "금융당국이 레버리지 ETF 투자한도를 100만원으로 제한하는 규제를 8월 21일부터 시행한다고 발표했다."),
            ("kbo-result", "kbo_hanwha", "한화 이글스", "한화 이글스 5-3 승리, 노시환 2홈런", "한화 이글스가 5-3으로 승리했고 노시환이 2홈런을 기록했다."),
            ("psat-competition", "psat_recruitment", "7급 공채", "지방공무원 7급 공채 경쟁률 71.5대1", "38명 선발에 1,461명이 지원해 경쟁률 71.5대1을 기록했다."),
        )
        for key, topic_id, query, title, summary in cases:
            assessment = self.assessment(key, topic_id, query, title, summary)
            self.assertNotIn("LOW_BRIEFING_MATERIALITY", assessment.reasons, title)
            self.assertTrue(assessment.qualified, (title, assessment.reasons, assessment.final_score))

    def test_intentional_materiality_rejection_is_not_false_empty_recall_risk(self) -> None:
        story = item("low-materiality-only", "kpop", "K-POP", "아이브, 새 앨범 콘셉트 포토 공개", "아이브가 8월 21일 새 앨범 콘셉트 포토를 공식 SNS에 공개했다.")
        result = select_clusters(
            (StoryCluster("kpop", (story,)),),
            TOPICS,
            limit=10,
            now=datetime.fromisoformat("2026-08-21T14:00:00+09:00"),
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.strong_rejected_candidates, 0)
        self.assertFalse(result.filter_collapse)
        self.assertEqual(result.audit[0]["reason"], "LOW_BRIEFING_MATERIALITY")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("briefing materiality patch applied")
