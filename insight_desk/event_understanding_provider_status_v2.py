from __future__ import annotations

"""Mechanical status contract for Event Understanding provider selection.

This module does not qualify providers and does not wire production. It only prevents an
unqualified, explicitly excluded, credential-blocked, stale-protocol, or inventory-blocked provider
from being selected as the Event Understanding owner.
"""

import json
from pathlib import Path
from typing import Any, Mapping

from insight_desk.core.contracts import ContractError


MINIMUM_COMPATIBILITY_PASS = "MINIMUM_COMPATIBILITY_PASS"
NOT_QUALIFIED = "NOT_QUALIFIED"
EXCLUDED = "EXCLUDED"
QUALIFICATION_BLOCKED_CREDENTIAL = "QUALIFICATION_BLOCKED_CREDENTIAL"
NO_ELIGIBLE_EXISTING_PROVIDER = "NO_ELIGIBLE_EXISTING_PROVIDER"
CANDIDATE_QUALIFICATION_BLOCKED = "CANDIDATE_QUALIFICATION_BLOCKED"
ELIGIBLE_CANDIDATE_AVAILABLE = "ELIGIBLE_CANDIDATE_AVAILABLE"
AWAITING_PROVIDER_QUALIFICATION = "AWAITING_PROVIDER_QUALIFICATION"
QUALIFIED_PROVIDER_SELECTED = "QUALIFIED_PROVIDER_SELECTED"
_ALLOWED_STATUSES = frozenset(
    {
        MINIMUM_COMPATIBILITY_PASS,
        NOT_QUALIFIED,
        EXCLUDED,
        QUALIFICATION_BLOCKED_CREDENTIAL,
    }
)
_ALLOWED_INVENTORY_STATUSES = frozenset(
    {
        NO_ELIGIBLE_EXISTING_PROVIDER,
        CANDIDATE_QUALIFICATION_BLOCKED,
        ELIGIBLE_CANDIDATE_AVAILABLE,
    }
)
_ALLOWED_QUALIFICATION_CONTRACT_STATUSES = frozenset(
    {AWAITING_PROVIDER_QUALIFICATION, QUALIFIED_PROVIDER_SELECTED}
)


def _qualification_protocol(raw: Mapping[str, Any], *, provider_id: str, active: int) -> int:
    protocol = raw.get("qualification_protocol")
    if type(protocol) is not int or protocol < 1 or protocol > active:
        raise ContractError(f"{provider_id}: qualification_protocol must identify a known protocol")
    return protocol


def validate_provider_status(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 2:
        raise ContractError("provider status schema_version must be 2")
    if payload.get("contract") != "event_understanding_v2":
        raise ContractError("provider status contract must be event_understanding_v2")
    if payload.get("structured_output_schema") != "event_understanding_schema_v2":
        raise ContractError("provider status structured output schema must be event_understanding_schema_v2")
    active_protocol = payload.get("active_qualification_protocol")
    if active_protocol != 3:
        raise ContractError("active qualification protocol must be 3")
    qualification_contract_status = payload.get("qualification_contract_status")
    if qualification_contract_status not in _ALLOWED_QUALIFICATION_CONTRACT_STATUSES:
        raise ContractError("qualification contract status is unsupported")
    if payload.get("full_production_correctness_claimed") is not False:
        raise ContractError("bounded qualification must not claim full production correctness")

    inventory_status = payload.get("provider_inventory_status")
    if inventory_status not in _ALLOWED_INVENTORY_STATUSES:
        raise ContractError("provider inventory status is unsupported")

    providers = payload.get("providers")
    if not isinstance(providers, Mapping) or not providers:
        raise ContractError("provider status requires providers mapping")

    for provider_id, raw in providers.items():
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ContractError("provider status id must be non-empty")
        if not isinstance(raw, Mapping):
            raise ContractError(f"{provider_id}: provider record must be an object")
        status = raw.get("status")
        if status not in _ALLOWED_STATUSES:
            raise ContractError(f"{provider_id}: unsupported provider status")
        if not isinstance(raw.get("provider"), str) or not str(raw.get("provider")).strip():
            raise ContractError(f"{provider_id}: provider name must be non-empty")
        if not isinstance(raw.get("model"), str) or not str(raw.get("model")).strip():
            raise ContractError(f"{provider_id}: model must be non-empty")
        responsibility = raw.get("existing_responsibility")
        if responsibility is not None and (
            not isinstance(responsibility, str) or not responsibility.strip()
        ):
            raise ContractError(f"{provider_id}: existing responsibility must be non-empty")

        evaluated_cases = raw.get("evaluated_cases", 0)
        if type(evaluated_cases) is not int or evaluated_cases < 0:
            raise ContractError(f"{provider_id}: evaluated_cases must be a non-negative integer")
        if status in {MINIMUM_COMPATIBILITY_PASS, NOT_QUALIFIED} and evaluated_cases > 0:
            _qualification_protocol(raw, provider_id=provider_id, active=active_protocol)
        if status == MINIMUM_COMPATIBILITY_PASS and evaluated_cases == 0:
            raise ContractError(f"{provider_id}: qualified provider must have evaluated cases")
        if status == QUALIFICATION_BLOCKED_CREDENTIAL:
            if evaluated_cases != 0:
                raise ContractError(
                    f"{provider_id}: credential-blocked qualification must evaluate zero cases"
                )
            if raw.get("preflight_result") != "NOT_CONFIGURED":
                raise ContractError(
                    f"{provider_id}: credential-blocked qualification must be NOT_CONFIGURED"
                )
            protocol = raw.get("qualification_protocol")
            if protocol is not None and protocol != active_protocol:
                raise ContractError(
                    f"{provider_id}: credential-blocked qualification must target active protocol"
                )

    selected = payload.get("selected_event_understanding_provider")
    production_wired = payload.get("production_wired")
    if not isinstance(production_wired, bool):
        raise ContractError("production_wired must be boolean")

    if selected is None:
        if production_wired:
            raise ContractError("production cannot be wired without a selected provider")
        if qualification_contract_status != AWAITING_PROVIDER_QUALIFICATION:
            raise ContractError("unselected provider state must await provider qualification")
        return

    if not isinstance(selected, str) or not selected.strip():
        raise ContractError("selected provider must be null or non-empty string")
    if qualification_contract_status != QUALIFIED_PROVIDER_SELECTED:
        raise ContractError("selected provider requires qualified-provider contract status")
    if inventory_status != ELIGIBLE_CANDIDATE_AVAILABLE:
        raise ContractError("provider inventory is not eligible for Event Understanding selection")
    selected_record = providers.get(selected)
    if not isinstance(selected_record, Mapping):
        raise ContractError("selected provider is absent from provider status")
    if selected_record.get("status") != MINIMUM_COMPATIBILITY_PASS:
        raise ContractError("selected Event Understanding provider is not qualified")
    if _qualification_protocol(
        selected_record,
        provider_id=selected,
        active=active_protocol,
    ) != active_protocol:
        raise ContractError("selected Event Understanding provider was qualified under a stale protocol")


def selected_provider(payload: Mapping[str, Any]) -> str | None:
    validate_provider_status(payload)
    selected = payload.get("selected_event_understanding_provider")
    return selected if isinstance(selected, str) else None


def load_provider_status(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractError("provider status JSON root must be an object")
    validate_provider_status(payload)
    return payload
