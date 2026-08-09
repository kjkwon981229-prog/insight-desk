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
    metrics = {
        "selected_total": len(stories),
        "generic_headline_count": 0,
        "generic_summary_count": 0,
        "other_event_count": 0,
        "uncertain_count": 0,
        "single_source_count": 0,
        "low_information_uncertain_count": 0,
    }
    for index, story in enumerate(stories, 1):
        if not isinstance(story, dict):
            errors.append(f"story {index} is not an object")
            continue
        headline = str(story.get("headline", ""))
        summary = str(story.get("summary", ""))
        if not headline or any(marker in headline for marker in generic_headline_markers):
            metrics["generic_headline_count"] += 1
            errors.append(f"story {index} has a generic headline")
        if not summary or any(marker in summary for marker in generic_summary_markers):
            metrics["generic_summary_count"] += 1
            errors.append(f"story {index} has a generic summary")
        if str(story.get("event_type", "OTHER")) == "OTHER":
            metrics["other_event_count"] += 1
            errors.append(f"story {index} has OTHER event type")
        certainty = str(story.get("certainty", ""))
        source_count = int(story.get("source_count", 0) or 0)
        concrete = int(story.get("concrete_fact_count", 0) or 0)
        if certainty == "uncertain":
            metrics["uncertain_count"] += 1
        if source_count <= 1:
            metrics["single_source_count"] += 1
        if certainty == "uncertain" and str(story.get("event_type", "OTHER")) == "OTHER" and source_count <= 1 and concrete == 0:
            metrics["low_information_uncertain_count"] += 1
            errors.append(f"story {index} is low-information uncertain")
        if not story.get("why_selected"):
            errors.append(f"story {index} has no why_selected")
        if not story.get("topic_id") and not story.get("topic"):
            errors.append(f"story {index} has no user-facing topic")
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
