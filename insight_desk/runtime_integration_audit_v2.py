from __future__ import annotations

"""Bounded, non-semantic health audit for production external integrations.

The audit distinguishes configuration from a successful live contract probe. It never sends a
push notification, never generates prose, and never asks an external model to interpret news.
Only integrations that can participate in the current runtime are probed; historical qualification
adapters are reported as outside the production path.
"""

from dataclasses import dataclass
from datetime import date, timedelta
import json
import os
from pathlib import Path
import socket
import ssl
import time
from typing import Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request

from insight_desk.acquisition.discovery import (
    BingNewsRssDiscovery,
    DiscoveryError,
    GdeltDocDiscovery,
    NaverNewsDiscovery,
)
from insight_desk.api import EcosClient, KosisClient, NaverApiClient, OpenDartClient
from insight_desk.api.naver import NaverCredentials
from insight_desk.core import FailureKind


_DEFAULT_CONFIG = Path("config/authoritative_sources.json")
_PASS = "PASS"
_NOT_CONFIGURED = "NOT_CONFIGURED"
_DISABLED = "DISABLED"
_NOT_ON_VISIBLE_PATH = "NOT_ON_VISIBLE_PATH"
_FAIL = "FAIL"

DECLARED_PRODUCTION_API_HOSTS = frozenset(
    {
        "api.cloudflare.com",
        "api.gdeltproject.org",
        "api.groq.com",
        "ecos.bok.or.kr",
        "generativelanguage.googleapis.com",
        "kosis.kr",
        "naverapihub.apigw.ntruss.com",
        "opendart.fss.or.kr",
        "www.bing.com",
    }
)


@dataclass(frozen=True, slots=True)
class IntegrationProbeSpec:
    integration_id: str
    role: str
    scope: str
    configured: bool
    active: bool
    required: bool = False
    inactive_status: str = _DISABLED
    probe: Callable[[], None] | None = None
    retry_delays: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.integration_id or not self.role or not self.scope:
            raise ValueError("integration probe identity/role/scope must be non-empty")
        if self.active and self.configured and self.probe is None:
            raise ValueError(f"{self.integration_id}: active configured integration needs a probe")
        if self.required and not self.active:
            raise ValueError(f"{self.integration_id}: required integration must be active")
        if any(delay < 0 for delay in self.retry_delays):
            raise ValueError(f"{self.integration_id}: retry delays must be non-negative")


def _url_error_kind(exc: urllib.error.URLError) -> str:
    reason = exc.reason
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "URLError_TIMEOUT"
    if isinstance(reason, socket.gaierror):
        return "URLError_DNS"
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return "URLError_TLS"
    if isinstance(reason, ConnectionRefusedError):
        return "URLError_CONNECTION_REFUSED"
    if isinstance(reason, ConnectionResetError):
        return "URLError_CONNECTION_RESET"
    if isinstance(reason, ConnectionError):
        return "URLError_CONNECTION"
    if isinstance(reason, OSError):
        return "URLError_OS"
    return "URLError_OTHER"


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, DiscoveryError):
        return exc.failure_kind.value
    if isinstance(exc, urllib.error.URLError):
        return _url_error_kind(exc)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    if isinstance(exc, ssl.SSLError):
        return "TLS"
    return type(exc).__name__


def _retryable_probe_failure(exc: Exception) -> bool:
    """Retry only failures that can change without a configuration or code change."""

    if isinstance(exc, DiscoveryError):
        return exc.failure_kind in {FailureKind.TRANSIENT_PROVIDER, FailureKind.INVALID_OUTPUT}
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, urllib.error.URLError):
        return isinstance(
            exc.reason,
            (
                TimeoutError,
                socket.timeout,
                socket.gaierror,
                ssl.SSLError,
                ConnectionError,
                OSError,
            ),
        )
    if isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError, ConnectionError, OSError)):
        return True
    cause = exc.__cause__
    return isinstance(cause, Exception) and cause is not exc and _retryable_probe_failure(cause)


def evaluate_integration_probes(
    specs: tuple[IntegrationProbeSpec, ...],
) -> dict[str, object]:
    if len({spec.integration_id for spec in specs}) != len(specs):
        raise ValueError("integration ids must be unique")

    results: dict[str, dict[str, object]] = {}
    configured_failures: list[str] = []
    unconfigured_optional: list[str] = []
    for spec in specs:
        attempted = False
        calls = 0
        error_kind: str | None = None
        if not spec.active:
            status = spec.inactive_status
        elif not spec.configured:
            status = _NOT_CONFIGURED
            if not spec.required:
                unconfigured_optional.append(spec.integration_id)
        else:
            attempted = True
            assert spec.probe is not None
            status = _FAIL
            for attempt in range(len(spec.retry_delays) + 1):
                calls += 1
                try:
                    spec.probe()
                except Exception as exc:  # no credential-bearing detail enters the audit
                    error_kind = _error_kind(exc)
                    if attempt < len(spec.retry_delays) and _retryable_probe_failure(exc):
                        time.sleep(spec.retry_delays[attempt])
                        continue
                    configured_failures.append(spec.integration_id)
                    break
                else:
                    status = _PASS
                    error_kind = None
                    break

        if spec.required and status != _PASS:
            configured_failures.append(spec.integration_id)
        results[spec.integration_id] = {
            "role": spec.role,
            "scope": spec.scope,
            "semantic_authority": False,
            "active": spec.active,
            "configured": spec.configured,
            "required": spec.required,
            "attempted": attempted,
            "calls": calls,
            "attempt_limit": len(spec.retry_delays) + 1,
            "recovered_after_retry": status == _PASS and calls > 1,
            "status": status,
            "error_kind": error_kind,
        }

    failures = sorted(set(configured_failures))
    return {
        "schema_version": 2,
        "semantic_authority": "exact_canonical_source_proposition",
        "external_semantic_provider_calls": 0,
        "status": _PASS if not failures else _FAIL,
        "all_configured_operational_routes_passed": not failures,
        "configured_failures": failures,
        "unconfigured_optional_routes": sorted(unconfigured_optional),
        "integrations": results,
    }


def _enabled(raw: object) -> bool:
    return isinstance(raw, Mapping) and raw.get("enabled") is True


def _explicit_flag(source: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = str(source.get(name, "true" if default else "false")).strip().casefold()
    if raw in {"true", "1", "yes", "on"}:
        return True
    if raw in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be an explicit boolean")


def _probe_naver(client: NaverApiClient) -> None:
    payload = client.search_news("인공지능", display=1, start=1, sort="date")
    if not isinstance(payload.get("items", []), list):
        raise ValueError("NAVER items must be a list")


def _probe_bing() -> None:
    BingNewsRssDiscovery().search("인공지능", topic_id="integration_probe", limit=1)


# Separate provider attempts into three windows. KOSIS already retries transport calls within one
# window; these delays protect the daily workflow from a short provider-wide outage while keeping
# every configured integration fail-closed when no real response succeeds.
_LIVE_PROBE_RETRY_DELAYS = (15.0, 45.0)


def _probe_gdelt() -> None:
    GdeltDocDiscovery().search("artificial intelligence", topic_id="integration_probe", limit=1)


def _month_period(anchor: date, delta: int) -> str:
    index = anchor.year * 12 + anchor.month - 1 + delta
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def _probe_ecos(client: EcosClient, config: Mapping[str, object]) -> None:
    datasets = config.get("datasets")
    if not isinstance(datasets, list) or not datasets or not isinstance(datasets[0], Mapping):
        raise ValueError("ECOS probe dataset is missing")
    dataset = datasets[0]
    anchor = date.today()
    payload = client.statistic_search(
        stat_code=str(dataset["stat_code"]),
        cycle=str(dataset["cycle"]),
        start_period=_month_period(anchor, -1),
        end_period=_month_period(anchor, 0),
        max_rows=1,
        item_code=str(dataset.get("item_code") or "") or None,
    )
    if not isinstance(payload, dict):
        raise ValueError("ECOS probe returned a non-object")


def _probe_kosis(client: KosisClient, config: Mapping[str, object]) -> None:
    datasets = config.get("datasets")
    if not isinstance(datasets, list) or not datasets or not isinstance(datasets[0], Mapping):
        raise ValueError("KOSIS probe dataset is missing")
    dataset = datasets[0]
    payload = client.statistics(
        org_id=str(dataset["org_id"]),
        table_id=str(dataset["tbl_id"]),
        object_l1=str(dataset["obj_l1"]),
        object_l2=str(dataset.get("obj_l2") or "") or None,
        item_id=str(dataset["itm_id"]),
        period_type=str(dataset["prd_se"]),
        max_periods=1,
    )
    if not isinstance(payload, (dict, list)):
        raise ValueError("KOSIS probe returned unsupported data")


def _probe_opendart(client: OpenDartClient, config: Mapping[str, object]) -> None:
    entities = config.get("entities")
    if not isinstance(entities, list) or not entities or not isinstance(entities[0], Mapping):
        raise ValueError("OpenDART probe entity is missing")
    entity = entities[0]
    end = date.today()
    payload = client.list_filings(
        corp_code=str(entity["corp_code"]),
        begin_date=end - timedelta(days=30),
        end_date=end,
        disclosure_type=str(config.get("disclosure_type") or "A"),
        page_no=1,
        page_count=1,
    )
    if not isinstance(payload, dict):
        raise ValueError("OpenDART probe returned a non-object")


def _probe_push_worker(worker_url: str) -> None:
    parsed = urllib.parse.urlparse(worker_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("push Worker URL must be HTTPS")
    health_url = worker_url.rstrip("/") + "/health"
    request = urllib.request.Request(
        health_url,
        headers={"Accept": "application/json", "User-Agent": "InsightDesk/2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError("push Worker health unavailable") from exc
    if not isinstance(payload, dict) or payload.get("publication_binding_version") != 2:
        raise ValueError("push Worker publication binding contract mismatch")


def build_runtime_integration_specs(
    *,
    env: Mapping[str, str] | None = None,
    config_path: Path = _DEFAULT_CONFIG,
) -> tuple[IntegrationProbeSpec, ...]:
    source = dict(os.environ) if env is None else dict(env)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("authoritative integration config must be an object")

    client_id = str(source.get("NCP_CLIENT_ID", "")).strip()
    client_secret = str(source.get("NCP_CLIENT_SECRET", "")).strip()
    if bool(client_id) != bool(client_secret):
        raise ValueError("NAVER discovery credentials are partial")
    naver_client = (
        NaverApiClient(NaverCredentials(client_id=client_id, client_secret=client_secret))
        if client_id and client_secret
        else None
    )
    cloudflare_account = str(source.get("CLOUDFLARE_ACCOUNT_ID", "")).strip()
    cloudflare_token = str(source.get("CLOUDFLARE_API_TOKEN", "")).strip()
    if bool(cloudflare_account) != bool(cloudflare_token):
        raise ValueError("Cloudflare verification credentials are partial")

    gdelt_enabled = _explicit_flag(source, "GDELT_DISCOVERY_ENABLED")
    ecos_config = config.get("ecos") if isinstance(config.get("ecos"), Mapping) else {}
    kosis_config = config.get("kosis") if isinstance(config.get("kosis"), Mapping) else {}
    dart_config = config.get("open_dart") if isinstance(config.get("open_dart"), Mapping) else {}
    ecos_client = EcosClient.from_environment(transport=None) if env is None else (
        EcosClient(str(source.get("ECOS_API_KEY", "")).strip())
        if str(source.get("ECOS_API_KEY", "")).strip()
        else None
    )
    kosis_client = KosisClient.from_environment(transport=None) if env is None else (
        KosisClient(str(source.get("KOSIS_API_KEY", "")).strip())
        if str(source.get("KOSIS_API_KEY", "")).strip()
        else None
    )
    dart_client = OpenDartClient.from_environment(transport=None) if env is None else (
        OpenDartClient(str(source.get("OPENDART_API_KEY", "")).strip())
        if str(source.get("OPENDART_API_KEY", "")).strip()
        else None
    )
    push_worker_url = str(source.get("PUSH_WORKER_URL", "")).strip()

    return (
        IntegrationProbeSpec(
            "bing_news_rss",
            role="news_discovery",
            scope="required_runtime",
            configured=True,
            active=True,
            required=True,
            probe=_probe_bing,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "naver_news_search",
            role="news_discovery",
            scope="conditional_runtime",
            configured=naver_client is not None,
            active=naver_client is not None,
            probe=(lambda: _probe_naver(naver_client)) if naver_client is not None else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "gdelt_doc",
            role="news_discovery",
            scope="opt_in_runtime",
            configured=gdelt_enabled,
            active=gdelt_enabled,
            inactive_status=_DISABLED,
            probe=_probe_gdelt if gdelt_enabled else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "ecos",
            role="authoritative_enrichment",
            scope="conditional_runtime",
            configured=ecos_client is not None,
            active=_enabled(ecos_config),
            probe=(lambda: _probe_ecos(ecos_client, ecos_config)) if ecos_client else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "kosis",
            role="authoritative_enrichment",
            scope="conditional_runtime",
            configured=kosis_client is not None,
            active=_enabled(kosis_config),
            probe=(lambda: _probe_kosis(kosis_client, kosis_config)) if kosis_client else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "opendart",
            role="authoritative_enrichment",
            scope="conditional_runtime",
            configured=dart_client is not None,
            active=_enabled(dart_config),
            probe=(lambda: _probe_opendart(dart_client, dart_config)) if dart_client else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "push_worker_health",
            role="publication_delivery",
            scope="conditional_runtime",
            configured=bool(push_worker_url),
            active=bool(push_worker_url),
            probe=(lambda: _probe_push_worker(push_worker_url)) if push_worker_url else None,
            retry_delays=_LIVE_PROBE_RETRY_DELAYS,
        ),
        IntegrationProbeSpec(
            "groq_generation",
            role="external_semantic_provider",
            scope="inactive_visible_path",
            configured=bool(str(source.get("GROQ_API_KEY", "")).strip()),
            active=False,
            inactive_status=_NOT_ON_VISIBLE_PATH,
        ),
        IntegrationProbeSpec(
            "cloudflare_workers_ai",
            role="external_semantic_provider",
            scope="inactive_visible_path",
            configured=bool(cloudflare_account) and bool(cloudflare_token),
            active=False,
            inactive_status=_NOT_ON_VISIBLE_PATH,
        ),
        IntegrationProbeSpec(
            "gemini_interactions",
            role="external_semantic_provider",
            scope="inactive_visible_path",
            configured=bool(str(source.get("GEMINI_API_KEY", "")).strip()),
            active=False,
            inactive_status=_NOT_ON_VISIBLE_PATH,
        ),
        IntegrationProbeSpec(
            "naver_search_trend",
            role="dormant_api_client",
            scope="no_production_caller",
            configured=naver_client is not None,
            active=False,
            inactive_status=_DISABLED,
        ),
        IntegrationProbeSpec(
            "qualification_provider_adapters",
            role="bounded_experiment_only",
            scope="not_exported_to_production",
            configured=False,
            active=False,
            inactive_status=_DISABLED,
        ),
        IntegrationProbeSpec(
            "configured_public_source_sites",
            role="reserved_configuration",
            scope="no_production_caller",
            configured=bool(config.get("public_sources")),
            active=False,
            inactive_status=_DISABLED,
        ),
    )


def audit_runtime_integrations(
    *,
    env: Mapping[str, str] | None = None,
    config_path: Path = _DEFAULT_CONFIG,
) -> dict[str, object]:
    return evaluate_integration_probes(
        build_runtime_integration_specs(env=env, config_path=config_path)
    )
