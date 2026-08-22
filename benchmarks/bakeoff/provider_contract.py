from __future__ import annotations

import json
from typing import Any


TEMPORAL_STATES = [
    "PLANNED",
    "ANNOUNCED_PROSPECTIVE",
    "RESUMING",
    "RESUMED",
    "COMPLETED",
    "CANCELLED",
]
EVENT_TYPES = [
    "REGULATION",
    "INDUSTRY_CHANGE",
    "ANNOUNCEMENT",
    "MARKET_MOVE",
    "ROSTER_PERSONNEL",
    "AWARD_CHART",
]
POLARITIES = ["POSITIVE", "NEGATIVE", "NEGATIVE_OUTCOME", "NEUTRAL", "MIXED"]


def _nullable(kind: str) -> dict[str, Any]:
    return {"type": [kind, "null"]}


def _nullable_enum(values: list[str]) -> dict[str, Any]:
    return {"type": ["string", "null"], "enum": [*values, None]}


def _nullable_array() -> dict[str, Any]:
    return {"type": ["array", "null"], "items": {"type": "string"}}


def _closed(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


TASK_SCHEMAS: dict[str, dict[str, Any]] = {
    "EVENT_EXTRACT": _closed(
        {
            "temporal_state": _nullable_enum(TEMPORAL_STATES),
            "duration": _nullable("string"),
            "event_date": _nullable("string"),
            "location": _nullable("string"),
            "cause": _nullable("string"),
            "participants": _nullable_array(),
        }
    ),
    "EVENT_OWNERSHIP": _closed(
        {
            "same_event_with": {"type": "array", "items": {"type": "string"}},
            "speaker_role": _nullable("string"),
            "action": _nullable("string"),
        }
    ),
    "SEMANTIC_CHECK": _closed(
        {
            "is_coherent_single_event": _nullable("boolean"),
            "context_noun_only_is_not_sufficient_action": _nullable("boolean"),
            "requires_direction_or_state_change_for_market_move": _nullable("boolean"),
            "participants": _nullable_array(),
            "starters": _nullable_array(),
            "action": _nullable("string"),
            "summary": _nullable("string"),
        }
    ),
    "MATERIAL_EVENT": _closed(
        {
            "is_material_event": {"type": "boolean"},
            "event_type": _nullable_enum(EVENT_TYPES),
            "action": _nullable("string"),
            "polarity": _nullable_enum(POLARITIES),
            "temporal_state": _nullable_enum(TEMPORAL_STATES),
        }
    ),
    "GENERATION": _closed(
        {
            "temporal_state": _nullable_enum(TEMPORAL_STATES),
            "headline": {"type": "string"},
            "summary": {"type": "string"},
        }
    ),
    "CLAIM_VERIFY": _closed(
        {
            "entailed": {"type": "boolean"},
        }
    ),
}


TASK_INSTRUCTIONS = {
    "EVENT_EXTRACT": (
        "Extract only temporal/lifecycle facts explicitly supported by the Korean news input. "
        "Distinguish duration from calendar event date, future/resuming from completed/resumed, "
        "and preserve location, cause, and named participants. For duration, event_date, location, "
        "and cause, copy the shortest explicit wording from the supplied input rather than resolving "
        "relative dates or paraphrasing. Use null when unsupported."
    ),
    "EVENT_OWNERSHIP": (
        "Decide which candidate IDs describe the same real-world event as target. Similar wording, "
        "the same teams, or a shared lead sentence is not enough when the event date, owner, cause, "
        "or core event differs. Also extract speaker_role/action when explicitly supported."
    ),
    "SEMANTIC_CHECK": (
        "Judge the semantic constraints from the supplied news text. Do not treat a context noun as "
        "an action. Do not invent missing participants or starters. Extract the explicit action when "
        "present. If a concise Korean summary is requested by the schema, keep it grammatical and "
        "fact-preserving."
    ),
    "MATERIAL_EVENT": (
        "Classify whether the input reports a concrete, current material event or outcome rather than "
        "commentary, generic trend/context, preview, biography, education, fan chatter, or stale context. "
        "Use only the event_type, polarity, and temporal_state labels permitted by the schema. For a "
        "positive event, extract a concise Korean action label supported by the input; otherwise null."
    ),
    "GENERATION": (
        "Write a concise natural Korean headline and one-sentence summary using only the supplied facts. "
        "Preserve subject, material object, event state, and time. Never convert an announcement or future "
        "plan into a completed event, or a completed event into a plan. Use only the temporal_state labels "
        "permitted by the schema and do not add unsupported facts."
    ),
    "CLAIM_VERIFY": (
        "Decide whether the hypothesis is fully entailed by the premise. Return entailed=true only when "
        "every material claim in the hypothesis is supported by the premise. Return false if the hypothesis "
        "changes subject, object, location, cause, event date, lifecycle/tense, certainty, polarity or "
        "negation, or adds any unsupported material fact. Do not use outside knowledge."
    ),
}


def schema_for(case: dict[str, Any]) -> dict[str, Any]:
    task = case["task"]
    try:
        return TASK_SCHEMAS[task]
    except KeyError as exc:
        raise ValueError(f"unsupported task: {task}") from exc


def prompt_for(case: dict[str, Any]) -> str:
    task = case["task"]
    instruction = TASK_INSTRUCTIONS[task]
    payload = {
        "case_id": case["id"],
        "task": task,
        "input": case["input"],
    }
    return (
        "You are an evaluation component for a Korean news intelligence system. "
        "Use only the provided input as evidence; do not use outside knowledge. "
        "Return only the requested structured result.\n\n"
        f"TASK INSTRUCTION:\n{instruction}\n\n"
        "INPUT JSON:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
