from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import cast

from insight_desk.runtime_integration_audit_v2 import audit_runtime_integrations


_KOSIS_PROBE_FIELDS_ENV = "INSIGHT_DESK_KOSIS_PROBE_OUTPUT_FIELDS"
_KOSIS_PROBE_FIELDS = "ORG_ID TBL_ID TBL_NM ITM_ID ITM_NM UNIT_NM PRD_SE PRD_DE DT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build/runtime-integration-audit.json")
    parser.add_argument("--strict-configured", action="store_true")
    args = parser.parse_args()

    # Match the field-selection shape emitted by KOSIS URL-generator examples while keeping the
    # marked probe bounded to one latest period. Normal enrichment runs in a separate process and
    # keeps the complete provider response contract.
    os.environ[_KOSIS_PROBE_FIELDS_ENV] = _KOSIS_PROBE_FIELDS
    payload = audit_runtime_integrations()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    integrations = payload["integrations"]
    if not isinstance(integrations, dict):
        raise ValueError("integration audit payload is missing integrations")
    typed_integrations = cast(dict[str, object], integrations)
    summary = " ".join(
        f"{name}={record['status']}"
        for name, record in typed_integrations.items()
        if isinstance(record, dict)
    )
    print(f"RUNTIME_INTEGRATION_AUDIT status={payload['status']} {summary}")
    if args.strict_configured and payload["all_configured_operational_routes_passed"] is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
