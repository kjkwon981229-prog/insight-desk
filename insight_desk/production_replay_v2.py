from __future__ import annotations

"""Recorded-edge replay of the actual Canonical V2 production entrypoint.

The replay deliberately does not reimplement semantic, identity, generation-policy, verification-
policy, publication, or PWA code. It replaces only nondeterministic/external edges (discovery,
acquisition, provider responses, and wall clock) and then calls
``scripts.phase11_daily_production.run_production`` exactly as production does.

Historic production artifacts did not retain full publisher article bodies. A fixture whose
``raw_article_body_complete`` flag is false therefore proves an exact-source-evidence replay, not a
full raw-body acquisition replay. The distinction is part of the returned report contract.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse

from insight_desk.acquisition import AcquisitionResult, ArticleCandidate, ExtractionQuality
from insight_desk.core import RawArticle, SourceProvenance, VerificationCheck
from insight_desk.generation import GeneratedDraft, GenerationRequest
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID
from scripts.validate_publication_identity import extract_publication_contract, validate_paths


_EXTERNAL_SECRET_NAMES = (
    "NCP_CLIENT_ID",
    "NCP_CLIENT_SECRET",
    "GROQ_API_KEY",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "GEMINI_API_KEY",
    "ECOS_API_KEY",
    "KOSIS_API_KEY",
    "OPENDART_API_KEY",
)


@dataclass(frozen=True, slots=True)
class RecordedReplayResult:
    state: Mapping[str, Any]
    audit: Mapping[str, Any]
    publication_manifest: Mapping[str, Any]
    publication_digest: str
    report: Mapping[str, Any]


class _RecordedDiscovery:
    def __init__(self, cases: tuple[dict[str, Any], ...], replay_clock: datetime) -> None:
        self._cases = cases
        self._clock = replay_clock
        self._stats = {
            "recorded_historical_source": {
                "calls": 0,
                "errors": 0,
                "empty": 0,
                "selected": 0,
                "candidates": 0,
            }
        }

    @property
    def route_stats(self) -> dict[str, dict[str, int]]:
        return {key: dict(value) for key, value in self._stats.items()}

    def search(
        self,
        query: str,
        *,
        topic_id: str,
        limit: int = 10,
    ) -> tuple[ArticleCandidate, ...]:
        stats = self._stats["recorded_historical_source"]
        stats["calls"] += 1
        matched = tuple(
            case
            for case in self._cases
            if case["query"] == query and case["topic_id"] == topic_id
        )[:limit]
        if not matched:
            stats["empty"] += 1
            return ()
        stats["selected"] += 1
        stats["candidates"] += len(matched)
        return tuple(
            ArticleCandidate(
                candidate_id=str(case["candidate_id"]),
                url=str(case["source_url"]),
                search_title=str(case["search_title"]),
                source_name=str(case["source_name"]),
                published_at=self._clock,
                topic_ids=(str(case["topic_id"]),),
                query=str(case["query"]),
                retrieved_via="recorded_historical_source",
            )
            for case in matched
        )


class _RecordedAcquisition:
    def __init__(self, cases: tuple[dict[str, Any], ...], replay_clock: datetime) -> None:
        self._by_candidate = {str(case["candidate_id"]): case for case in cases}
        self.fetcher = SimpleNamespace(method_id="recorded-source")
        self.primary_extractor = SimpleNamespace(method_id="exact-source-excerpt")
        self.fallback_extractor = SimpleNamespace(method_id="unused-fallback")
        self.fallback_renderer = SimpleNamespace(method_id="unused-renderer")

    def acquire(self, candidate: ArticleCandidate) -> AcquisitionResult:
        case = self._by_candidate[candidate.candidate_id]
        body = str(case["source_excerpt"])
        host = (urlparse(candidate.url).hostname or candidate.source_name).lower()
        article = RawArticle(
            article_id=candidate.candidate_id,
            provenance=SourceProvenance(
                source_id=f"web:{host}",
                source_name=candidate.source_name,
                url=candidate.url,
                retrieved_via="recorded_historical_source+exact_source_excerpt",
                fetched_at=candidate.published_at or datetime.now(timezone.utc),
                published_at=candidate.published_at,
            ),
            title=candidate.search_title,
            body=body,
            topic_ids=candidate.topic_ids,
            query=candidate.query,
        )
        return AcquisitionResult(
            article=article,
            extraction_method="recorded-source+exact-source-excerpt",
            fallback_used=False,
            quality=ExtractionQuality(
                acceptable=True,
                character_count=sum(not char.isspace() for char in body),
                reasons=(),
            ),
            source_html_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )


class _RecordedGroqClient:
    @classmethod
    def configured(cls, *, model_id: str) -> bool:
        del model_id
        return True

    @classmethod
    def from_env(cls, model_id: str):
        del model_id
        return cls()


class _RecordedGenerator:
    def __init__(self, _client: object, cases: tuple[dict[str, Any], ...]) -> None:
        self._by_source = {
            str(case["source_excerpt"]): case
            for case in cases
        }

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        source = request.evidence_text.strip()
        case = self._by_source.get(source)
        if case is None:
            raise ValueError("recorded replay has no generator response for evidence bytes")
        generated = case["recorded_generation"]
        return GeneratedDraft(
            event_id=request.event.event_id,
            headline=str(generated["headline"]),
            summary=str(generated["summary"]),
            evidence_ids=request.evidence_ids,
        )


class _RecordedVerifier:
    def __init__(self, verifier_id: str, model_id: str) -> None:
        self.verifier_id = verifier_id
        self.model_id = model_id
        self.calls = 0

    @property
    def route_stats(self) -> dict[str, dict[str, int]]:
        return {
            self.model_id: {
                "calls": self.calls,
                "supported": self.calls,
            }
        }

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        del claim_text, evidence_text
        self.calls += 1
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=True,
            zero_cost=True,
        )


class _RecordedCloudflare:
    @classmethod
    def from_env(cls):
        return _RecordedVerifier(
            CLOUDFLARE_VERIFIER_ID,
            "recorded:cloudflare-primary",
        )


class _RecordedLocalNli:
    @classmethod
    def transformers_default(cls):
        return _RecordedVerifier(
            LOCAL_NLI_VERIFIER_ID,
            "recorded:local-nli-secondary",
        )


class _NoNetworkMethod:
    def __init__(self, method_id: str) -> None:
        self.method_id = method_id


@contextmanager
def _recorded_edges(
    *,
    cases: tuple[dict[str, Any], ...],
    replay_clock: datetime,
) -> Iterator[None]:
    from scripts import phase11_daily_production as production

    core = production._core
    discovery = _RecordedDiscovery(cases, replay_clock)
    acquisition = _RecordedAcquisition(cases, replay_clock)
    real_datetime = core.datetime

    class ReplayDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return replay_clock.replace(tzinfo=None)
            return replay_clock.astimezone(tz)

    replacements = {
        "datetime": ReplayDateTime,
        "default_news_discovery": lambda: discovery,
        "UrlLibHtmlFetcher": lambda **_kwargs: _NoNetworkMethod("recorded-source"),
        "TrafilaturaExtractor": lambda **_kwargs: _NoNetworkMethod("exact-source-excerpt"),
        "PlaywrightHtmlRenderer": lambda **_kwargs: _NoNetworkMethod("unused-renderer"),
        "AcquisitionPipeline": lambda **_kwargs: acquisition,
        "GroqFreeClient": _RecordedGroqClient,
        "Groq20BBriefingGenerator": lambda client: _RecordedGenerator(client, cases),
        "CloudflareClaimVerifier": _RecordedCloudflare,
        "LocalNliVerifier": _RecordedLocalNli,
    }
    originals = {name: getattr(core, name) for name in replacements}
    env_snapshot = {name: os.environ.get(name) for name in _EXTERNAL_SECRET_NAMES}
    try:
        for name in _EXTERNAL_SECRET_NAMES:
            os.environ.pop(name, None)
        for name, value in replacements.items():
            setattr(core, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(core, name, value)
        for name, value in env_snapshot.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _load_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("production replay fixture must be a JSON object")
    if payload.get("replay_mode") != "historical_exact_source_excerpt_replay":
        raise ValueError("unsupported production replay mode")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("production replay fixture requires cases")
    return payload


def run_recorded_production_replay(
    *,
    fixture_path: Path,
    work_dir: Path,
) -> RecordedReplayResult:
    """Run one deterministic historical replay through the actual public production entrypoint."""

    from scripts import phase11_daily_production as production

    payload = _load_fixture(fixture_path)
    cases = tuple(dict(case) for case in payload["cases"])
    replay_clock = datetime.fromisoformat(str(payload["replay_clock"]))
    if replay_clock.tzinfo is None or replay_clock.utcoffset() is None:
        raise ValueError("replay clock must be timezone-aware")

    work_dir.mkdir(parents=True, exist_ok=True)
    topics_path = work_dir / "topics.json"
    output_dir = work_dir / "site"
    state_path = work_dir / "run-state.json"
    audit_path = work_dir / "production-audit.json"
    topics_path.write_text(
        json.dumps(
            {"schema_version": 1, "topics": payload["topics"]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with _recorded_edges(cases=cases, replay_clock=replay_clock):
        state = production.run_production(
            topics_path=topics_path,
            output_dir=output_dir,
            state_path=state_path,
            audit_path=audit_path,
        )

    if state.get("publish") is not True:
        raise AssertionError("recorded production replay produced no publishable briefing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    identity = validate_paths(
        html_path=output_dir / "index.html",
        state_path=state_path,
        audit_path=audit_path,
    )
    digest, manifest = extract_publication_contract(
        (output_dir / "index.html").read_text(encoding="utf-8")
    )
    if digest != identity["publication_digest"]:
        raise AssertionError("replay validator and PWA publication digest disagree")

    expected = payload.get("expected", {})
    report: dict[str, Any] = {
        "schema_version": 1,
        "phase": 5,
        "status": payload.get("phase5_status", "PARTIAL"),
        "replay_mode": payload["replay_mode"],
        "raw_article_body_complete": payload.get("raw_article_body_complete") is True,
        "source_artifact": payload.get("source_artifact", {}),
        "candidate_count": len(cases),
        "published_entries": int(state.get("published_entries", 0)),
        "publication_digest": digest,
        "publication_ids": identity["publication_ids"],
        "canonical_parent_events": int(audit.get("canonical_contract", {}).get("parent_events", 0)),
        "identity_same_event": int(audit.get("identity_stats", {}).get("same_event", 0)),
        "canonical_bundle_validated": audit.get("canonical_contract", {}).get("validated") is True,
        "pwa_state_audit_digest_bound": True,
        "expected": expected,
        "network_calls": 0,
        "provider_mode": "recorded_external_edges_real_production_pipeline",
    }
    (work_dir / "replay-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return RecordedReplayResult(
        state=state,
        audit=audit,
        publication_manifest=manifest,
        publication_digest=digest,
        report=report,
    )
