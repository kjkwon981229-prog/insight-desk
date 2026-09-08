from __future__ import annotations

"""Validate that one deployed PWA is bound to one exact VerifiedPublication set."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any


PUBLICATION_CONTRACT_ID = "insight-desk-publication-contract"
PUBLICATION_CONTRACT_VERSION = 2


class _PublicationContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self._buffer: list[str] = []
        self.contracts: list[tuple[dict[str, str], str]] = []
        self._attrs: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script" or self._capture:
            return
        values = {key: value or "" for key, value in attrs}
        if values.get("id") != PUBLICATION_CONTRACT_ID:
            return
        self._capture = True
        self._buffer = []
        self._attrs = values

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "script" or not self._capture:
            return
        assert self._attrs is not None
        self.contracts.append((self._attrs, "".join(self._buffer)))
        self._capture = False
        self._buffer = []
        self._attrs = None


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def extract_publication_contract(html: str) -> tuple[str, dict[str, Any]]:
    parser = _PublicationContractParser()
    parser.feed(html)
    parser.close()
    if len(parser.contracts) != 1:
        raise ValueError(
            f"PUBLICATION_IDENTITY_CONTRACT_COUNT:{len(parser.contracts)}"
        )
    attrs, raw_payload = parser.contracts[0]
    if attrs.get("type") != "application/json":
        raise ValueError("PUBLICATION_IDENTITY_SCRIPT_TYPE")
    attr_digest = attrs.get("data-publication-digest", "")
    if len(attr_digest) != 64 or any(char not in "0123456789abcdef" for char in attr_digest):
        raise ValueError("PUBLICATION_IDENTITY_HTML_DIGEST_FORMAT")
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("PUBLICATION_IDENTITY_HTML_JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("PUBLICATION_IDENTITY_HTML_OBJECT")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if computed != attr_digest:
        raise ValueError("PUBLICATION_IDENTITY_HTML_DIGEST_MISMATCH")
    return computed, payload


def validate_identity(
    *,
    html: str,
    state: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    digest, manifest = extract_publication_contract(html)
    if state.get("publish") is not True:
        raise ValueError("PUBLICATION_IDENTITY_STATE_NOT_PUBLISHED")
    if manifest.get("version") != PUBLICATION_CONTRACT_VERSION:
        raise ValueError("PUBLICATION_IDENTITY_MANIFEST_VERSION")
    if state.get("publication_contract_version") != PUBLICATION_CONTRACT_VERSION:
        raise ValueError("PUBLICATION_IDENTITY_STATE_VERSION")
    if audit.get("publication_contract_version") != PUBLICATION_CONTRACT_VERSION:
        raise ValueError("PUBLICATION_IDENTITY_AUDIT_VERSION")

    briefing_id = manifest.get("briefing_id")
    if not isinstance(briefing_id, str) or not briefing_id:
        raise ValueError("PUBLICATION_IDENTITY_BRIEFING_ID")
    if state.get("briefing_id") != briefing_id:
        raise ValueError("PUBLICATION_IDENTITY_STATE_BRIEFING_MISMATCH")

    audit_identity = audit.get("publication_identity")
    if not isinstance(audit_identity, dict):
        raise ValueError("PUBLICATION_IDENTITY_AUDIT_MISSING")
    if audit_identity.get("briefing_id") != briefing_id:
        raise ValueError("PUBLICATION_IDENTITY_AUDIT_BRIEFING_MISMATCH")
    if state.get("publication_digest") != digest:
        raise ValueError("PUBLICATION_IDENTITY_STATE_DIGEST_MISMATCH")
    if audit_identity.get("sha256") != digest:
        raise ValueError("PUBLICATION_IDENTITY_AUDIT_DIGEST_MISMATCH")

    publications = manifest.get("publications")
    if not isinstance(publications, list) or not publications:
        raise ValueError("PUBLICATION_IDENTITY_PUBLICATIONS_EMPTY")
    publication_ids: list[str] = []
    event_ids: list[str] = []
    for record in publications:
        if not isinstance(record, dict):
            raise ValueError("PUBLICATION_IDENTITY_RECORD_OBJECT")
        if "headline" in record or "summary" in record:
            raise ValueError("PUBLICATION_IDENTITY_VISIBLE_PROSE_LEAK")
        publication_id = record.get("publication_id")
        event_id = record.get("event_id")
        if not isinstance(publication_id, str) or not publication_id:
            raise ValueError("PUBLICATION_IDENTITY_PUBLICATION_ID")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("PUBLICATION_IDENTITY_EVENT_ID")
        publication_ids.append(publication_id)
        event_ids.append(event_id)
    if len(publication_ids) != len(set(publication_ids)):
        raise ValueError("PUBLICATION_IDENTITY_DUPLICATE_PUBLICATION_ID")
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("PUBLICATION_IDENTITY_DUPLICATE_EVENT_ID")

    if state.get("publication_ids") != publication_ids:
        raise ValueError("PUBLICATION_IDENTITY_STATE_IDS_MISMATCH")
    if audit_identity.get("publication_ids") != publication_ids:
        raise ValueError("PUBLICATION_IDENTITY_AUDIT_IDS_MISMATCH")
    if state.get("published_entries") != len(publications):
        raise ValueError("PUBLICATION_IDENTITY_STATE_COUNT_MISMATCH")

    canonical_contract = audit.get("canonical_contract")
    if not isinstance(canonical_contract, dict) or canonical_contract.get("validated") is not True:
        raise ValueError("PUBLICATION_IDENTITY_CANONICAL_BUNDLE_NOT_VALIDATED")
    if canonical_contract.get("verified_publications") != len(publications):
        raise ValueError("PUBLICATION_IDENTITY_CANONICAL_COUNT_MISMATCH")

    return {
        "briefing_id": briefing_id,
        "publication_digest": digest,
        "publication_ids": publication_ids,
        "publication_count": len(publications),
    }


def validate_paths(*, html_path: Path, state_path: Path, audit_path: Path) -> dict[str, Any]:
    return validate_identity(
        html=html_path.read_text(encoding="utf-8"),
        state=_load_json(state_path),
        audit=_load_json(audit_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    result = validate_paths(
        html_path=args.html,
        state_path=args.state,
        audit_path=args.audit,
    )
    print(
        "PUBLICATION_IDENTITY_VALID "
        f"briefing_id={result['briefing_id']} "
        f"digest={result['publication_digest']} "
        f"publications={result['publication_count']}"
    )


if __name__ == "__main__":
    main()
