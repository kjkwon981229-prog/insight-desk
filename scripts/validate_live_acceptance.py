from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insight_desk.pipeline.semantics import (
    ACTION_TERMS,
    compact,
    contains_action,
    metric_summary_preserves_entity_binding,
    metric_observations,
    same_lifecycle_signatures,
    subject_boundary_is_clean,
    summary_information_gain,
)
from insight_desk.pipeline.synthesis import editorial_text_issues

_MARKET_ACTIONS = {
    "강보합세",
    "급등",
    "급락",
    "상승",
    "하락",
    "강세",
    "약세",
    "보합",
    "증가",
    "감소",
    "확대",
    "축소",
    "돌파",
    "변동",
}


def validate(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stories = payload.get("selected_stories", [])
    errors: list[str] = []
    if not isinstance(stories, list):
        return ["selected_stories is not a list"]
    if len(stories) > 10:
        errors.append("selected story count exceeds maximum 10")
    funnel = payload.get("funnel")
    selection_audit = payload.get("selection_audit")
    if funnel is not None and not isinstance(funnel, dict):
        errors.append("candidate funnel is not an object")
    if selection_audit is not None and not isinstance(selection_audit, list):
        errors.append("selection audit is not a list")
    strong_rejected_from_funnel = 0
    qualified_from_funnel = 0
    if isinstance(funnel, dict):
        required_funnel_fields = {
            "intent_pass",
            "event_pass",
            "evidence_pass",
            "novelty_pass",
            "qualified",
            "selected",
            "synthesis_veto",
            "strong_rejected",
        }
        for topic_id, topic_funnel in funnel.items():
            if not isinstance(topic_funnel, dict):
                errors.append(f"funnel for {topic_id} is not an object")
                continue
            missing = sorted(required_funnel_fields - set(topic_funnel))
            if missing:
                errors.append(f"funnel for {topic_id} is missing diagnostics: {','.join(missing)}")
                continue
            strong_rejected_from_funnel += int(topic_funnel.get("strong_rejected", 0) or 0)
            qualified_from_funnel += int(topic_funnel.get("qualified", 0) or 0)
    strong_rejected = max(int(payload.get("strong_rejected_candidates", 0) or 0), strong_rejected_from_funnel)
    if strong_rejected > 0:
        errors.append("strong upstream candidates were rejected by a downstream gate")
    if not stories:
        health = str(payload.get("editorial_health", "") or "")
        if health == "FILTER_COLLAPSE" or strong_rejected > 0 or qualified_from_funnel > 0:
            errors.append("zero-story result is a filter collapse, not a valid empty day")
        elif health not in {"VALID_EMPTY_DAY", "OK"}:
            errors.append("zero-story result has no explicit valid-empty classification")
    generic_headline_markers = ("관련 보도", "관련 소식", "관련 기사", "관련 뉴스")
    generic_summary_markers = (
        "단일 검색 결과만 확인되어",
        "공통으로 확인되는 세부 사실은 제한적이다",
        "세부 내용은 추가 확인이 필요하다",
        "여러 매체에서 같은 핵심 내용이 확인됐다",
        "여러 보도에서 같은 핵심 내용이 확인됐다",
        "공식 자료를 인용한 보도가 확인됐다",
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
        "semantic_error_count": 0,
        "publisher_diversity_error_count": 0,
        "temporal_role_error_count": 0,
        "sentence_completeness_error_count": 0,
        "quote_balance_error_count": 0,
        "subject_boundary_error_count": 0,
        "event_ownership_error_count": 0,
        "fact_provenance_error_count": 0,
        "semantic_role_error_count": 0,
    }
    signatures: list[str] = []
    for index, story in enumerate(stories, 1):
        if not isinstance(story, dict):
            errors.append(f"story {index} is not an object")
            continue
        headline = str(story.get("headline", ""))
        summary = str(story.get("summary", ""))
        headline_issues = editorial_text_issues(headline)
        summary_issues = editorial_text_issues(summary)
        quote_issues = set(headline_issues + summary_issues).intersection(
            {"UNMATCHED_QUOTE", "UNMATCHED_BRACKET"}
        )
        if quote_issues:
            metrics["quote_balance_error_count"] += len(quote_issues)
            errors.append(f"story {index} has unmatched display punctuation")
        completeness_issues = set(summary_issues).intersection(
            {"BARE_NUMERIC_END", "DANGLING_CLAUSE", "MALFORMED_SUBJECT_BOUNDARY"}
        )
        if completeness_issues:
            metrics["sentence_completeness_error_count"] += len(completeness_issues)
            errors.append(
                f"story {index} has incomplete or malformed summary copy: "
                f"{','.join(sorted(completeness_issues))}"
            )
        if story.get("rank") not in (None, index):
            errors.append(f"story {index} has non-sequential editorial rank")
        if not headline or any(marker in headline for marker in generic_headline_markers):
            metrics["generic_headline_count"] += 1
            errors.append(f"story {index} has a generic headline")
        if not summary or any(
            summary.strip() == marker or summary.strip().startswith(marker)
            for marker in generic_summary_markers
        ):
            metrics["generic_summary_count"] += 1
            errors.append(f"story {index} has a generic summary")
        if headline and summary and not summary_information_gain(headline, summary):
            errors.append(f"story {index} summary has no information gain over headline")
        if any(marker in headline or marker in summary for marker in ("...", "…", "··")):
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
        try:
            final_score = float(story.get("final_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            final_score = 0.0
        if final_score < 55.0:
            errors.append(f"story {index} is below the editorial quality floor")
        facts = story.get("facts")
        if isinstance(facts, dict):
            audited_event_type = str(story.get("event_type", "")).strip()
            synthesized_event_type = str(facts.get("event_type", "")).strip()
            if audited_event_type and synthesized_event_type and audited_event_type != synthesized_event_type:
                errors.append(
                    f"story {index} event type disagrees with synthesized facts: "
                    f"{audited_event_type} != {synthesized_event_type}"
                )
            facts_signature = str(facts.get("event_signature", "")).strip()
            story_signature = str(story.get("event_signature", "")).strip()
            if story_signature and not facts_signature:
                errors.append(f"story {index} is missing canonical facts event signature")
            elif story_signature and facts_signature and story_signature != facts_signature:
                errors.append(f"story {index} event signature disagrees with synthesized facts")
            audit_event_id = str(story.get("canonical_event_id", "")).strip()
            facts_event_id = str(facts.get("canonical_event_id", "")).strip()
            if audit_event_id and facts_event_id and audit_event_id != facts_event_id:
                errors.append(
                    f"story {index} canonical event identity disagrees with synthesized facts"
                )
            conflict_state = str(facts.get("conflict_state", "NO_CONFLICT") or "NO_CONFLICT")
            if conflict_state not in {"NO_CONFLICT", "CONFIRMED_MATCH"}:
                errors.append(f"story {index} has unresolved authority/event conflict: {conflict_state}")
            action = str(facts.get("action", "")).strip()
            subject = str(facts.get("subject", "")).strip()
            cause = str(facts.get("cause", "")).strip()
            condition = str(facts.get("condition", "")).strip()
            policy_object = str(facts.get("object", "")).strip()
            owner_ids = {
                str(value).strip()
                for value in facts.get("event_owner_ids", ()) or ()
                if str(value).strip()
            }
            fact_evidence_ids = {
                str(value).strip()
                for value in facts.get("fact_evidence_ids", ()) or ()
                if str(value).strip()
            }
            representative_evidence_id = str(
                facts.get("representative_evidence_id", "")
            ).strip()
            if source_count > 0 and not owner_ids:
                metrics["event_ownership_error_count"] += 1
                errors.append(f"story {index} has no canonical-event evidence owners")
            if representative_evidence_id and representative_evidence_id not in owner_ids:
                metrics["event_ownership_error_count"] += 1
                errors.append(f"story {index} representative does not own the canonical event")
            if owner_ids and not representative_evidence_id:
                metrics["event_ownership_error_count"] += 1
                errors.append(f"story {index} has no event-owning representative")
            if not fact_evidence_ids:
                metrics["fact_provenance_error_count"] += 1
                errors.append(f"story {index} has no fact evidence provenance")
            elif not fact_evidence_ids.issubset(owner_ids):
                metrics["fact_provenance_error_count"] += 1
                errors.append(f"story {index} contains facts owned by a different event")

            role_errors: list[str] = []
            if cause and compact(cause) == compact(action):
                role_errors.append("cause occupies the action role")
            if event_type == "SPORTS_INTERRUPTION" and compact(action) in {
                "폭염",
                "더위",
                "고온",
                "열파",
                "우천",
                "폭우",
            }:
                role_errors.append("weather cause occupies the action role")
            if policy_object and compact(policy_object) == compact(action):
                role_errors.append("policy object occupies the action role")
            if event_type == "POLICY" and compact(action) in {"기준금리", "정책금리"}:
                role_errors.append("policy noun occupies the action role")
            if condition and compact(condition) and compact(condition) in compact(subject):
                role_errors.append("condition remains inside the subject")
            if event_type == "POLICY" and any(
                marker in subject for marker in ("없다면", "없으면", "있다면", "있으면")
            ) and not condition:
                role_errors.append("conditional clause was not separated from the subject")
            for detail in dict.fromkeys(role_errors):
                metrics["semantic_role_error_count"] += 1
                errors.append(f"story {index} semantic role failure: {detail}")
            if not subject_boundary_is_clean(event_type, subject):
                metrics["subject_boundary_error_count"] += 1
                errors.append(f"story {index} stores an audience phrase inside its subject")
            if action in ACTION_TERMS and not contains_action(f"{headline} {summary}", action):
                errors.append(f"story {index} has an action unsupported at a lexical boundary")
            if event_type in {"MARKET", "MARKET_MOVE", "STATISTIC", "EARNINGS"} and action and action not in _MARKET_ACTIONS:
                errors.append(f"story {index} uses a non-market action for a metric event")

            if event_type := str(story.get("event_type", "")):
                if event_type in {"MARKET", "MARKET_MOVE", "STATISTIC", "EARNINGS"}:
                    binding_error = not metric_summary_preserves_entity_binding(headline, summary)
                    observations = []
                    seen_observations = set()
                    for observation in metric_observations(f"{headline} {summary}"):
                        key = (observation.instrument, observation.value, observation.direction)
                        if key not in seen_observations:
                            seen_observations.add(key)
                            observations.append(observation)
                    key_numbers = tuple(str(value) for value in facts.get("key_numbers", ()) if value)
                    for value in key_numbers:
                        if any(char.isdigit() for char in value) and value not in summary:
                            errors.append(f"story {index} drops a bound metric value from its summary")
                    if observations and subject and subject != observations[0].instrument:
                        errors.append(f"story {index} metric subject is not the first bound instrument")
                    for change in facts.get("key_changes", ()) or ():
                        change_text = str(change)
                        tokens = change_text.split()
                        if len(tokens) >= 2 and not all(token in summary for token in tokens[:2]):
                            binding_error = True
                    if binding_error:
                        errors.append(f"story {index} loses metric entity/direction binding")
            temporal_payload = facts.get("temporal_facts", ())
            temporal_by_role: dict[str, set[str]] = {}
            if isinstance(temporal_payload, list):
                for temporal in temporal_payload:
                    if not isinstance(temporal, dict):
                        errors.append(f"story {index} has a malformed temporal fact")
                        continue
                    role = str(temporal.get("role", "")).strip()
                    value = str(temporal.get("value", "")).strip()
                    if role and value:
                        temporal_by_role.setdefault(role, set()).add(value)
            fact_date = str(facts.get("date", "")).strip()
            date_values: set[str] = set()
            for role in (
                "EVENT_DATE",
                "SCHEDULE_DATE",
                "START_DATE",
                "END_DATE",
                "RESUMPTION_DATE",
            ):
                date_values.update(temporal_by_role.get(role, set()))
            duration_values = set(temporal_by_role.get("DURATION", set()))
            duration_values.update(temporal_by_role.get("ELAPSED_DURATION", set()))
            temporal_errors: list[str] = []
            if temporal_by_role and fact_date and fact_date not in date_values:
                temporal_errors.append("date is not backed by a calendar/event temporal role")
            if fact_date and fact_date in duration_values and fact_date not in date_values:
                temporal_errors.append("duration was promoted to an event date")
            temporal_state = str(facts.get("temporal_state", "")).strip()
            resumption_dates = temporal_by_role.get("RESUMPTION_DATE", set())
            if temporal_state in {"RESUMING", "RESUMED"} and resumption_dates:
                if fact_date not in resumption_dates:
                    temporal_errors.append("resumption state lost its bound resumption date")
            for duration in duration_values - date_values:
                if duration and any(
                    f"{duration}에" in value.replace(" ", "")
                    for value in (headline, summary)
                ):
                    temporal_errors.append("synthesis rendered a duration as a calendar date")
            for detail in dict.fromkeys(temporal_errors):
                metrics["temporal_role_error_count"] += 1
                errors.append(f"story {index} temporal contract failure: {detail}")
        audited_conflict = str(story.get("conflict_state", "NO_CONFLICT") or "NO_CONFLICT")
        if audited_conflict not in {"NO_CONFLICT", "CONFIRMED_MATCH"}:
            errors.append(f"story {index} has unresolved audit conflict: {audited_conflict}")
        trend_relationship = str(story.get("trend_relationship", "")).strip()
        trend_matches = story.get("trend_matches")
        if trend_relationship and (
            not isinstance(trend_matches, list) or not trend_matches
        ):
            errors.append(f"story {index} has a trend label without matched trend groups")
        if isinstance(trend_matches, list):
            for match in trend_matches:
                if not isinstance(match, dict):
                    errors.append(f"story {index} has a malformed trend match")
                    continue
                trend_state = str(match.get("state", "")).strip()
                if trend_state not in {"", "RISE", "FALL", "NO_MEANINGFUL_CHANGE", "INSUFFICIENT_COMPARISON"}:
                    errors.append(f"story {index} has an unknown trend state")
                if trend_relationship and "상승" in trend_relationship and trend_state and trend_state != "RISE":
                    errors.append(f"story {index} labels a non-rising trend as rising")
                if trend_relationship and "둔화" in trend_relationship and trend_state and trend_state != "FALL":
                    errors.append(f"story {index} labels a non-falling trend as slowing")
        if certainty == "uncertain":
            metrics["uncertain_count"] += 1
        if source_count <= 1:
            metrics["single_source_count"] += 1
        publisher_diversity = int(story.get("publisher_diversity", source_count) or 0)
        if publisher_diversity > source_count:
            metrics["publisher_diversity_error_count"] += 1
            errors.append(f"story {index} publisher diversity exceeds source count")
        if certainty == "uncertain" and str(story.get("event_type", "OTHER")) == "OTHER" and source_count <= 1 and concrete == 0:
            metrics["low_information_uncertain_count"] += 1
            errors.append(f"story {index} is low-information uncertain")
        if source_count <= 1 and not story.get("official_source") and "추가 확인이 필요하다" in summary:
            errors.append(f"story {index} exposes unresolved single-source uncertainty")
        if not story.get("why_selected"):
            errors.append(f"story {index} has no why_selected")
        signature = str(story.get("event_signature", "")).strip()
        if signature:
            signatures.append(signature)
        if not story.get("topic_id") and not story.get("topic"):
            errors.append(f"story {index} has no user-facing topic")
    distinct_signatures: list[str] = []
    duplicate_event_count = 0
    for signature in signatures:
        if any(same_lifecycle_signatures(signature, seen) for seen in distinct_signatures):
            duplicate_event_count += 1
        else:
            distinct_signatures.append(signature)
    metrics["duplicate_event_count"] = duplicate_event_count
    if duplicate_event_count:
        errors.append("selected stories contain duplicate event signatures")
    metrics["semantic_error_count"] = len(errors)
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
