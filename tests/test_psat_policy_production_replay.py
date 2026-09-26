from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from insight_desk.production_replay_v2 import run_recorded_production_replay


_FIXTURE = Path(__file__).parent / "fixtures" / "psat_20260827_official_replay_v1.json"
_OTHER_CATEGORIES = Path(__file__).parent / "fixtures" / "phase5_real_source_replay_v1.json"
_SEMANTIC_AVAILABLE = importlib.util.find_spec("kiwipiepy") is not None


def _case(case_id: str, title: str, body: str, url: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "topic_id": "psat_recruitment",
        "query": "PSAT",
        "candidate_id": f"replay:{case_id}",
        "source_name": "합성 테스트 자료",
        "source_url": url,
        "search_title": title,
        "source_excerpt": body,
        "source_excerpt_provenance": "Synthetic regression sentence; no claim of a real future publication",
        "recorded_generation": {"headline": title, "summary": body},
    }


def _replay(cases: list[dict[str, object]], *, clock: str | None = None):
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    fixture["cases"] = cases
    if clock is not None:
        fixture["replay_clock"] = clock
    with tempfile.TemporaryDirectory() as root:
        path = Path(root)
        fixture_path = path / "fixture.json"
        fixture_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
        try:
            return run_recorded_production_replay(fixture_path=fixture_path, work_dir=path / "out")
        except AssertionError as exc:
            audit_path = path / "out" / "production-audit.json"
            detail = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
            raise AssertionError(f"{exc}: {json.dumps(detail, ensure_ascii=False)}") from exc


@unittest.skipUnless(_SEMANTIC_AVAILABLE, "production semantic-local runtime required")
class PsatPolicyProductionReplayTests(unittest.TestCase):
    def test_other_categories_keep_original_selection_and_source_fidelity(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            result = run_recorded_production_replay(
                fixture_path=_OTHER_CATEGORIES, work_dir=Path(root) / "other-topics"
            )
        publications = result.publication_manifest["publications"]
        self.assertEqual(result.state["published_entries"], 3)
        self.assertEqual({item["topic"] for item in publications},
                         {"economy", "kpop", "kbo_hanwha"})
        self.assertEqual(result.report["identity_same_event"], 1)
        self.assertTrue(result.report["canonical_bundle_validated"])

    def test_august_official_reform_survives_all_real_production_gates(self) -> None:
        result = _replay([json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"][0]])
        stats = result.audit["topic_stats"]["psat_recruitment"]
        self.assertEqual(stats["acquired_articles"], 1)
        self.assertEqual(stats["material_events"], 1)
        self.assertEqual(stats["included_events"], 1)
        self.assertEqual(stats["published_entries"], 1)
        self.assertEqual(result.report["network_calls"], 0)
        self.assertEqual(len(result.publication_manifest["publications"]), 1)
        self.assertEqual(result.publication_manifest["publications"][0]["topic"],
                         "psat_recruitment")
        self.assertTrue(result.report["pwa_state_audit_digest_bound"])

    def test_official_exam_date_change_is_material(self) -> None:
        case = _case(
            "schedule-change", "2027년도 공직적격성평가(PSAT) 심화 시험일 변경",
            "인사혁신처는 2027년도 공직적격성평가(PSAT) 심화 시험일을 2월 20일에서 2월 27일로 변경하고 원서접수 기간을 1월 5일부터 1월 9일까지로 조정한다고 공고했다.",
            "https://fixture.invalid/psat/schedule-change",
        )
        result = _replay([case], clock="2026-11-15T06:00:00+00:00")
        self.assertGreaterEqual(result.audit["topic_stats"]["psat_recruitment"]["material_events"], 1)
        self.assertEqual(result.audit["topic_stats"]["psat_recruitment"]["published_entries"], 1)

    def test_promotion_does_not_replace_official_reform(self) -> None:
        official = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"][0]
        promotion = _case(
            "promotion", "5급 공채 PSAT 학원 할인 이벤트",
            "A학원은 5급 공채 PSAT 문제집 출간을 기념해 수강생에게 20% 할인과 합격 후기 특강을 제공한다고 밝혔다.",
            "https://fixture.invalid/psat/promotion",
        )
        result = _replay([official, promotion])
        self.assertEqual(result.audit["topic_stats"]["psat_recruitment"]["published_entries"], 1)
        self.assertEqual(result.publication_manifest["publications"][0]["primary_source_url"],
                         official["source_url"])

    def test_promotion_quoting_an_official_policy_is_still_commercial(self) -> None:
        official = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"][0]
        promotion = _case(
            "quoted-promotion", "5급 공채 PSAT 개편 대비 학원 설명회",
            "A학원은 인사혁신처의 5급 공채 PSAT 제도 개편 발표를 소개하는 유료 특강을 할인 판매한다고 밝혔다.",
            "https://fixture.invalid/psat/quoted-promotion",
        )
        result = _replay([official, promotion])
        self.assertEqual(result.audit["topic_stats"]["psat_recruitment"]["published_entries"], 1)

    def test_copied_media_version_cannot_multiply_official_publication(self) -> None:
        official = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"][0]
        copied = deepcopy(official)
        copied.update({
            "case_id": "copied-media", "candidate_id": "replay:copied-media",
            "source_name": "복제 보도", "source_url": "https://fixture.invalid/psat/copied-media",
        })
        result = _replay([official, copied])
        self.assertEqual(result.audit["topic_stats"]["psat_recruitment"]["published_entries"], 1)
        self.assertEqual(len(result.publication_manifest["publications"]), 1)
        self.assertIn("content_fingerprint_already_published",
                      [item.get("reason") for item in result.audit["attempts"]])

    def test_hypothetical_november_details_are_a_new_material_publication(self) -> None:
        case = _case(
            "future-details", "2027년도 공직적격성평가(PSAT) 세부 시행계획 공고",
            "인사혁신처는 2027년도 공직적격성평가(PSAT) 세부 시행계획에 심화 시험 2월 20일, 기본 시험 7월 17일 및 원서접수 1월 5일부터 9일까지를 확정했다.",
            "https://fixture.invalid/psat/future-details",
        )
        result = _replay([case], clock="2026-11-15T06:00:00+00:00")
        self.assertGreaterEqual(result.audit["topic_stats"]["psat_recruitment"]["material_events"], 1)
        self.assertEqual(result.audit["topic_stats"]["psat_recruitment"]["published_entries"], 1)
        initial = _replay([json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"][0]])
        self.assertNotEqual(result.publication_manifest["publications"][0]["event_id"],
                            initial.publication_manifest["publications"][0]["event_id"])


if __name__ == "__main__":
    unittest.main()
