from __future__ import annotations

import json
from typing import Any

from insight_desk.core import Certainty, FailureKind, OutcomePolarity, TemporalState
from insight_desk.providers import GROQ_20B, GroqFreeClient, ProviderTransportError

from .facts import FactDraft, FactExtractionRequest


_FACT_KEYS = frozenset(
    {
        "subject",
        "action",
        "object",
        "temporal_state",
        "certainty",
        "polarity",
        "event_date",
        "location",
        "cause",
        "participants",
        "evidence_ids",
    }
)


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _nullable_enum(values: list[str]) -> dict[str, Any]:
    return {"type": ["string", "null"], "enum": [*values, None]}


FACT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "action": {"type": "string"},
                    "object": _nullable_string(),
                    "temporal_state": _nullable_enum([state.value for state in TemporalState]),
                    "certainty": {
                        "type": "string",
                        "enum": [certainty.value for certainty in Certainty],
                    },
                    "polarity": _nullable_enum([polarity.value for polarity in OutcomePolarity]),
                    "event_date": _nullable_string(),
                    "location": _nullable_string(),
                    "cause": _nullable_string(),
                    "participants": {"type": "array", "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": sorted(_FACT_KEYS),
                "additionalProperties": False,
            },
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}


class Groq20BFactExtractor:
    """Evidence-bound FactExtractorPort adapter for the frozen zero-cost Groq 20B lane.

    Provider output remains untrusted. The adapter validates the closed schema again locally,
    rejects foreign evidence ids and duplicate semantic drafts, and requires source-literal
    subjects, material objects, dates, locations, causes, and participants. The action may be a
    concise semantic normalization, but it cannot create evidence or merge event identity.
    """

    extractor_id = "groq-gpt-oss-20b-fact-extractor-v1"
    max_facts = 12

    def __init__(self, client: GroqFreeClient) -> None:
        if client.model_id != GROQ_20B:
            raise ValueError("fact extraction canary is frozen to Groq GPT-OSS 20B")
        self.client = client

    @classmethod
    def from_env(cls, *, delay_seconds: float = 2.1) -> "Groq20BFactExtractor":
        return cls(GroqFreeClient.from_env(GROQ_20B, delay_seconds=delay_seconds))

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        response = self.client.structured_json(
            prompt=self._prompt(request),
            schema=FACT_EXTRACTION_SCHEMA,
            schema_name="insight_desk_fact_extract_v1",
            system_prompt=(
                "Extract only explicit event facts from the supplied evidence. "
                "Use no outside knowledge. Follow the JSON schema exactly and output no commentary."
            ),
        )
        if set(response) != {"facts"}:
            self._invalid("fact extractor root keys do not match contract")
        raw_facts = response["facts"]
        if not isinstance(raw_facts, list):
            self._invalid("facts must be a JSON array")
        if len(raw_facts) > self.max_facts:
            self._invalid(f"fact extractor returned more than {self.max_facts} facts")

        allowed = {span.evidence_id: span for span in request.evidence}
        drafts: list[FactDraft] = []
        seen: set[tuple[Any, ...]] = set()

        for index, item in enumerate(raw_facts, start=1):
            if not isinstance(item, dict) or set(item) != _FACT_KEYS:
                self._invalid(f"fact {index} keys do not match closed contract")

            subject = self._text(item["subject"], f"fact {index} subject")
            action = self._text(item["action"], f"fact {index} action")
            object_value = self._optional_text(item["object"], f"fact {index} object")
            event_date = self._optional_text(item["event_date"], f"fact {index} event_date")
            location = self._optional_text(item["location"], f"fact {index} location")
            cause = self._optional_text(item["cause"], f"fact {index} cause")

            evidence_ids = self._string_tuple(item["evidence_ids"], f"fact {index} evidence_ids")
            if not evidence_ids:
                self._invalid(f"fact {index} must cite evidence")
            if len(evidence_ids) != len(set(evidence_ids)):
                self._invalid(f"fact {index} contains duplicate evidence ids")
            for evidence_id in evidence_ids:
                if evidence_id not in allowed:
                    self._invalid(f"fact {index} cites evidence outside extraction request")

            participants = self._string_tuple(item["participants"], f"fact {index} participants")
            if len(participants) != len(set(participants)):
                self._invalid(f"fact {index} contains duplicate participants")

            temporal_state = self._enum_or_none(
                TemporalState,
                item["temporal_state"],
                f"fact {index} temporal_state",
            )
            certainty = self._enum_required(Certainty, item["certainty"], f"fact {index} certainty")
            polarity = self._enum_or_none(
                OutcomePolarity,
                item["polarity"],
                f"fact {index} polarity",
            )

            cited_text = "\n".join(allowed[evidence_id].text for evidence_id in evidence_ids)
            for field_name, literal in (
                ("subject", subject),
                ("object", object_value),
                ("event_date", event_date),
                ("location", location),
                ("cause", cause),
            ):
                if literal is not None and literal not in cited_text:
                    self._invalid(f"fact {index} {field_name} is not source-literal evidence")
            for participant in participants:
                if participant not in cited_text:
                    self._invalid(f"fact {index} participant is not source-literal evidence")

            draft = FactDraft(
                draft_id=f"groq20b-{index:04d}",
                subject=subject,
                action=action,
                object=object_value,
                temporal_state=temporal_state,
                certainty=certainty,
                polarity=polarity,
                event_date=event_date,
                location=location,
                cause=cause,
                participants=participants,
                evidence_ids=evidence_ids,
            )
            draft.validate_against(request)

            signature = (
                draft.subject,
                draft.action,
                draft.object,
                draft.temporal_state,
                draft.certainty,
                draft.polarity,
                draft.event_date,
                draft.location,
                draft.cause,
                draft.participants,
                draft.evidence_ids,
            )
            if signature in seen:
                self._invalid("fact extractor returned a duplicate semantic draft")
            seen.add(signature)
            drafts.append(draft)

        return tuple(drafts)

    @staticmethod
    def _prompt(request: FactExtractionRequest) -> str:
        evidence = [
            {"evidence_id": span.evidence_id, "text": span.text}
            for span in request.evidence
        ]
        payload = {
            "article_id": request.article.article_id,
            "topic_id": request.topic_id,
            "evidence": evidence,
        }
        return (
            "Extract concrete event facts explicitly stated in the evidence windows below. "
            "Do not use outside knowledge and do not infer missing names, dates, locations, causes, "
            "objects, participants, or outcomes. A bare topic noun, entity name, numeric value, "
            "commentary, biography, preview, or generic trend without an explicit event action or "
            "state change is not an event fact; return no fact rather than inventing an action. "
            "Keep future/planned/announced/resuming/resumed/completed/cancelled lifecycle distinctions "
            "exact. Copy subject, material object, event_date, location, cause, and every participant "
            "as the shortest explicit wording verbatim from cited evidence; only action may be a concise "
            "semantic normalization. Every fact must cite only supplied evidence_ids that support the "
            "whole fact. Keep separate events as separate facts and never merge identity here.\n\n"
            "EVIDENCE JSON:\n"
            + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )

    @staticmethod
    def _text(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            Groq20BFactExtractor._invalid(f"{label} must be non-empty string")
        return value.strip()

    @staticmethod
    def _optional_text(value: Any, label: str) -> str | None:
        if value is None:
            return None
        return Groq20BFactExtractor._text(value, label)

    @staticmethod
    def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
        if not isinstance(value, list):
            Groq20BFactExtractor._invalid(f"{label} must be an array")
        return tuple(Groq20BFactExtractor._text(item, label) for item in value)

    @staticmethod
    def _enum_required(enum_type, value: Any, label: str):
        if not isinstance(value, str):
            Groq20BFactExtractor._invalid(f"{label} must be string")
        try:
            return enum_type(value)
        except ValueError:
            Groq20BFactExtractor._invalid(f"{label} is outside contract enum")

    @staticmethod
    def _enum_or_none(enum_type, value: Any, label: str):
        if value is None:
            return None
        return Groq20BFactExtractor._enum_required(enum_type, value, label)

    @staticmethod
    def _invalid(detail: str):
        raise ProviderTransportError(failure_kind=FailureKind.INVALID_OUTPUT, detail=detail)
