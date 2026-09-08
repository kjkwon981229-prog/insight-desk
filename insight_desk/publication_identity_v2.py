from __future__ import annotations

"""Stable public identity for one verified briefing publication set."""

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from insight_desk.core import VerifiedPublication


PUBLICATION_IDENTITY_VERSION = 2


@dataclass(frozen=True, slots=True)
class PublicationIdentityRecord:
    publication_id: str
    event_id: str
    topic: str
    source_ids: tuple[str, ...]
    primary_source_url: str
    claim_ids: tuple[str, ...]
    verification_check_ids: tuple[str, ...]
    render_mode: str
    event_time: str | None
    publication_time: str | None
    parent_event_id: str | None
    authoritative_fact_ids: tuple[str, ...]

    @classmethod
    def from_verified(cls, publication: VerifiedPublication) -> "PublicationIdentityRecord":
        return cls(
            publication_id=publication.publication_id,
            event_id=publication.event_id,
            topic=publication.topic,
            source_ids=publication.source_ids,
            primary_source_url=publication.primary_source_url,
            claim_ids=publication.claim_ids,
            verification_check_ids=publication.verification_check_ids,
            render_mode=publication.render_mode.value,
            event_time=publication.event_time,
            publication_time=(
                publication.publication_time.isoformat()
                if publication.publication_time is not None
                else None
            ),
            parent_event_id=publication.parent_event_id,
            authoritative_fact_ids=publication.authoritative_fact_ids,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "publication_id": self.publication_id,
            "event_id": self.event_id,
            "topic": self.topic,
            "source_ids": list(self.source_ids),
            "primary_source_url": self.primary_source_url,
            "claim_ids": list(self.claim_ids),
            "verification_check_ids": list(self.verification_check_ids),
            "render_mode": self.render_mode,
            "event_time": self.event_time,
            "publication_time": self.publication_time,
            "parent_event_id": self.parent_event_id,
            "authoritative_fact_ids": list(self.authoritative_fact_ids),
        }


@dataclass(frozen=True, slots=True)
class PublicationIdentityManifest:
    briefing_id: str
    publications: tuple[PublicationIdentityRecord, ...]
    version: int = PUBLICATION_IDENTITY_VERSION

    @classmethod
    def from_verified(
        cls,
        briefing_id: str,
        publications: tuple[VerifiedPublication, ...],
    ) -> "PublicationIdentityManifest":
        if not briefing_id.strip():
            raise ValueError("briefing_id must be non-empty")
        if not publications:
            raise ValueError("publication identity requires at least one publication")
        ids = tuple(publication.publication_id for publication in publications)
        if len(ids) != len(set(ids)):
            raise ValueError("publication identity requires unique publication ids")
        return cls(
            briefing_id=briefing_id,
            publications=tuple(
                PublicationIdentityRecord.from_verified(publication)
                for publication in publications
            ),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "briefing_id": self.briefing_id,
            "publications": [publication.as_dict() for publication in self.publications],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def publication_ids(self) -> tuple[str, ...]:
        return tuple(publication.publication_id for publication in self.publications)


def manifest_from_mapping(
    briefing_id: str,
    event_ids: tuple[str, ...],
    publication_by_event: Mapping[str, VerifiedPublication],
) -> PublicationIdentityManifest:
    publications: list[VerifiedPublication] = []
    for event_id in event_ids:
        publication = publication_by_event.get(event_id)
        if publication is None:
            raise ValueError(f"missing VerifiedPublication for PWA event: {event_id}")
        publications.append(publication)
    return PublicationIdentityManifest.from_verified(briefing_id, tuple(publications))
