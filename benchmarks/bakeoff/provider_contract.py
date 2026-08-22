from __future__ import annotations

import json
from typing import Any


def _nullable(kind: str) -> dict[str, Any]:
    return {"type": [kind, "null"]}


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
            "temporal_state": _nullable("string"),
            "duration": _nullable("string"),
            "event_date": _nullable("string"),
            "location": _nullable("string"),
            "cause": _nullable("string"),
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
            "summary": _nullable("string"),
        }
    ),
    "MATERIAL_EVENT": _closed(
        {
            "is_material_event": {"type": "boolean"},
            "event_type": _nullable("string"),
            "action": _nullable("string"),
            "polarity": _nullable("string"),
            "temporal_state": _nullable("string"),
        }
    ),
    "GENERATION": _closed(
        {
            "temporal_state": _nullable("string"),
            "headline": {"type": "string"},
            "summary": {"type": "string"},
        }
    ),
}


TASK_INSTRUCTIONS = {
    "EVENT_EXTRACT": (
        "Extract only temporal/lifecycle facts explicitly supported by the Korean news input. "
        "Distinguish duration from calendar event date, future/resuming from completed/resumed, "
        "and preserve location and cause. Use null when unsupported."
    ),
    "EVENT_OWNERSHIP": (
        "Decide which candidate IDs describe the same real-world event as target. Similar wording, "
        "the same teams, or a shared lead sentence is not enough when the event date, owner, cause, "
        "or core event differs. Also extract speaker_role/action when explicitly supported."
    ),
    "SEMANTIC_CHECK": (
        "Judge the semantic constraints from the supplied news text. Do not treat a context noun as "
        "an action. Do not invent missing participants or starters. If a concise Korean summary is "
        "requested by the schema, keep it grammatical and fact-preserving."
    ),
    "MATERIAL_EVENT": (
        "Classify whether the input reports a concrete, current material event or outcome rather than "
        "commentary, generic trend/context, preview, biography, education, fan chatter, or stale context. "
        "For positives extract event_type/action/polarity/temporal_state only when supported; otherwise null."
    ),
    "GENERATION": (
        "Write a concise natural Korean headline and one-sentence summary using only the supplied facts. "
        "Preserve subject, material object, event state, and time. Never convert an announcement or future "
        "plan into a completed event, or a completed event into a plan. Do not add unsupported facts."
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
