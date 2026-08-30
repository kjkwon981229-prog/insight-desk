from __future__ import annotations

"""Mechanical PHASE 4 migration gate for Event Understanding production rewiring.

This module does not perform semantic qualification and does not modify active production.
It prevents a future provider PASS from being mistaken for permission to wire production while
legacy semantic bypasses are still present.
"""

import json
from pathlib import Path
from typing import Any, Mapping

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    validate_provider_status,
)


CONTRACT = "event_understanding_phase4_migration_gate_v1"


def validate_migration_gate(payload: Mapping[str, Any], *, root: Path | None = None) -> None:
    if payload.get("schema_version") != 1:
        raise ContractError("migration gate schema_version must be 1")
    if payload.get("contract") != CONTRACT:
        raise ContractError(f"migration gate contract must be {CONTRACT}")
    allowed = payload.get("production_rewire_allowed")
    if not isinstance(allowed, bool):
        raise ContractError("production_rewire_allowed must be boolean")

    blockers = payload.get("runtime_blockers")
    if not isinstance(blockers, Mapping) or not blockers:
        raise ContractError("migration gate requires runtime_blockers")

    active_count = 0
    for blocker_id, raw in blockers.items():
        if not isinstance(blocker_id, str) or not blocker_id.strip():
            raise ContractError("migration blocker id must be non-empty")
        if not isinstance(raw, Mapping):
            raise ContractError(f"{blocker_id}: blocker record must be an object")
        active = raw.get("active")
        if not isinstance(active, bool):
            raise ContractError(f"{blocker_id}: active must be boolean")
        path = raw.get("path")
        evidence = raw.get("evidence")
        if not isinstance(path, str) or not path.strip():
            raise ContractError(f"{blocker_id}: path must be non-empty")
        if not isinstance(evidence, str) or not evidence:
            raise ContractError(f"{blocker_id}: evidence must be non-empty")
        if active:
            active_count += 1
            if root is not None:
                source_path = root / path
                if not source_path.is_file():
                    raise ContractError(f"{blocker_id}: evidence path missing: {path}")
                source = source_path.read_text(encoding="utf-8")
                if evidence not in source:
                    raise ContractError(
                        f"{blocker_id}: blocker marked active but source evidence is absent"
                    )

    required = payload.get("required_before_rewire")
    if not isinstance(required, list) or not required or any(
        not isinstance(item, str) or not item.strip() for item in required
    ):
        raise ContractError("migration gate requires non-empty required_before_rewire entries")

    if active_count and allowed:
        raise ContractError("production rewire cannot be allowed while runtime blockers are active")
    if active_count == 0 and not allowed:
        raise ContractError("migration gate must be explicitly opened when all blockers are inactive")


def assert_production_rewire_allowed(
    provider_status: Mapping[str, Any],
    migration_gate: Mapping[str, Any],
    *,
    root: Path | None = None,
) -> str:
    validate_provider_status(provider_status)
    validate_migration_gate(migration_gate, root=root)

    if provider_status.get("provider_inventory_status") != ELIGIBLE_CANDIDATE_AVAILABLE:
        raise ContractError("Event Understanding provider inventory is not eligible for production")
    selected = provider_status.get("selected_event_understanding_provider")
    providers = provider_status.get("providers")
    if not isinstance(selected, str) or not selected:
        raise ContractError("Event Understanding production requires a selected provider")
    if not isinstance(providers, Mapping):
        raise ContractError("provider status requires providers mapping")
    selected_record = providers.get(selected)
    if not isinstance(selected_record, Mapping) or selected_record.get("status") != MINIMUM_COMPATIBILITY_PASS:
        raise ContractError("selected Event Understanding provider lacks minimum compatibility pass")
    if migration_gate.get("production_rewire_allowed") is not True:
        raise ContractError("PHASE 4 runtime bypasses still block production rewiring")
    return selected


def load_migration_gate(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractError("migration gate JSON root must be an object")
    validate_migration_gate(payload, root=root)
    return payload
