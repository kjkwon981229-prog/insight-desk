from __future__ import annotations

import json
import sys
from pathlib import Path


def validate(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stories = payload.get("selected_stories", [])
    errors: list[str] = []
    if not isinstance(stories, list):
        return ["selected_stories is not a list"]
    if len(stories) > 10:
        errors.append("selected story count exceeds maximum 10")
    generic_headline_markers = ("관련 보도", "관련 소식", "관련 기사", "관련 뉴스")
    generic_summary_markers = (
        "단일 검색 결과만 확인되어",
        "공통으로 확인되는 세부 사실은 제한적이다",
        "세부 내용은 추가 확인이 필요하다",
    )
    low_value_event_types = {
        "LOW_VALUE_APPEARANCE",
        "ROUTINE_SCHEDULE",
        "ROUTINE_MARKET_QUOTE",
        "MERCHANDISE",
    }
    metrics = {
        "selected_total": len(stories),
        "generic_headline_count": 0,
        "generic_summary_count": 0,
        "truncated_copy_count": 0,
        "other_event_count": 0,
        "uncertain_count": 0,
        "single_source_count": 0,
        "duplicate_event_count": 0,
        "low_information_uncertain_count": 0,
    }
    signatures: dict[str, int] = {}
    for index, story in enumerate(stories, 1):
        if not isinstance(story, dict):
            errors.append(f"story {index} is not an object")
            continue
        headline = str(story.get("headline", ""))
        summary = str(story.get("summary", ""))
        if story.get("rank") not in (None, index):
            errors.append(f"story {index} has non-sequential editorial rank")
        if not headline or any(marker in headline for marker in generic_headline_markers):
            metrics["generic_headline_count"] += 1
            errors.append(f"story {index} has a generic headline")
        if not summary or any(marker in summary for marker in generic_summary_markers):
            metrics["generic_summary_count"] += 1
            errors.append(f"story {index} has a generic summary")
        if any(marker in headline or marker in summary for marker in ("...", "…")):
            metrics["truncated_copy_count"] += 1
            errors.append(f"story {index} leaks truncated source copy")
        event_type = str(story.get("event_type", "OTHER"))
        if event_type == "OTHER":
            metrics["other_event_count"] += 1
            errors.append(f"story {index} has OTHER event type")
        if event_type in low_value_event_types:
            errors.append(f"story {index} has low-value event type {event_type}")
        certainty = str(story.get("certainty", ""))
        source_count = int(story.get("source_count", 0) or 0)
        concrete = int(story.get("concrete_fact_count", 0) or 0)
        facts = story.get("facts")
        if isinstance(facts, dict):
            audited_event_type = str(story.get("event_type", "")).strip()
            synthesized_event_type = str(facts.get("event_type", "")).strip()
            if audited_event_type and synthesized_event_type and audited_event_type != synthesized_event_type:
                errors.append(
                    f"story {index} event type disagrees with synthesized facts: "
                    f"{audited_event_type} != {synthesized_event_type}"
                )
        trend_relationship = str(story.get("trend_relationship", "")).strip()
        trend_matches = story.get("trend_matches")
        if trend_relationship and (
            not isinstance(trend_matches, list) or not trend_matches
        ):
            errors.append(f"story {index} has a trend label without matched trend groups")
        if certainty == "uncertain":
            metrics["uncertain_count"] += 1
        if source_count <= 1:
            metrics["single_source_count"] += 1
        if certainty == "uncertain" and str(story.get("event_type", "OTHER")) == "OTHER" and source_count <= 1 and concrete == 0:
            metrics["low_information_uncertain_count"] += 1
            errors.append(f"story {index} is low-information uncertain")
        if source_count <= 1 and not story.get("official_source") and "추가 확인이 필요하다" in summary:
            errors.append(f"story {index} exposes unresolved single-source uncertainty")
        if not story.get("why_selected"):
            errors.append(f"story {index} has no why_selected")
        signature = str(story.get("event_signature", "")).strip()
        if signature:
            signatures[signature] = signatures.get(signature, 0) + 1
        if not story.get("topic_id") and not story.get("topic"):
            errors.append(f"story {index} has no user-facing topic")
    duplicate_event_count = sum(count - 1 for count in signatures.values() if count > 1)
    metrics["duplicate_event_count"] = duplicate_event_count
    if duplicate_event_count:
        errors.append("selected stories contain duplicate event signatures")
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return errors


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "build/live-acceptance.json")
    errors = validate(path)
    if errors:
        for error in errors:
            print(f"::error::{error}")
        return 1
    print(f"live editorial acceptance passed: {len(json.loads(path.read_text(encoding='utf-8')).get('selected_stories', []))} stories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
