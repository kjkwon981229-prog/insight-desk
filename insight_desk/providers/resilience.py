from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import Callable, Protocol

from insight_desk.core import VerificationCheck


class ClaimVerifierRoute(Protocol):
    verifier_id: str
    model_id: str

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck: ...


class ProviderAvailabilityState(StrEnum):
    HEALTHY = "healthy"
    TRANSIENT_FAILURE = "transient_failure"
    RATE_LIMITED = "rate_limited"
    DAILY_QUOTA_EXHAUSTED = "daily_quota_exhausted"
    CONFIG_MISSING = "config_missing"
    INVALID_OUTPUT = "invalid_output"
    OPEN_CIRCUIT = "open_circuit"


@dataclass(slots=True)
class ProviderCircuit:
    provider_id: str
    clock: Callable[[], float] = time.monotonic
    default_rate_limit_cooldown: float = 60.0
    state: ProviderAvailabilityState = ProviderAvailabilityState.HEALTHY
    open_reason: ProviderAvailabilityState | None = None
    retry_at: float | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if self.default_rate_limit_cooldown < 0:
            raise ValueError("default_rate_limit_cooldown must be >= 0")

    def allows_call(self) -> bool:
        if self.state is ProviderAvailabilityState.OPEN_CIRCUIT:
            return False
        if self.state in {ProviderAvailabilityState.RATE_LIMITED, ProviderAvailabilityState.TRANSIENT_FAILURE}:
            if self.retry_at is None or self.clock() < self.retry_at:
                return False
            self.reset()
        return self.state is ProviderAvailabilityState.HEALTHY

    def reset(self) -> None:
        self.state = ProviderAvailabilityState.HEALTHY
        self.open_reason = None
        self.retry_at = None

    def record_success(self) -> None:
        self.reset()

    def record_error_code(self, error_code: str | None, *, retry_after_seconds: float | None = None) -> None:
        code = (error_code or "").strip().casefold()
        if code.startswith("free_quota_exhausted") or code.startswith("daily_quota_exhausted"):
            self.state = ProviderAvailabilityState.OPEN_CIRCUIT
            self.open_reason = ProviderAvailabilityState.DAILY_QUOTA_EXHAUSTED
            self.retry_at = None
            return
        if code.startswith("rate_limited"):
            cooldown = retry_after_seconds if retry_after_seconds is not None else self.default_rate_limit_cooldown
            self.state = ProviderAvailabilityState.RATE_LIMITED
            self.open_reason = None
            self.retry_at = self.clock() + max(0.0, cooldown)
            return
        if code.startswith("transient_provider") or code.startswith("verifier_exception"):
            self.state = ProviderAvailabilityState.TRANSIENT_FAILURE
            self.open_reason = None
            self.retry_at = self.clock() + self.default_rate_limit_cooldown
            return
        if code.startswith("missing_provider") or code.startswith("config_missing"):
            self.state = ProviderAvailabilityState.OPEN_CIRCUIT
            self.open_reason = ProviderAvailabilityState.CONFIG_MISSING
            self.retry_at = None
            return
        if code:
            self.state = ProviderAvailabilityState.OPEN_CIRCUIT
            self.open_reason = ProviderAvailabilityState.INVALID_OUTPUT
            self.retry_at = None


@dataclass(frozen=True, slots=True)
class UnavailableClaimVerifier:
    verifier_id: str
    model_id: str = "unavailable"
    error_code: str = "config_missing"

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        del claim_text, evidence_text
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=None,
            error_code=self.error_code,
            zero_cost=True,
        )


@dataclass(slots=True)
class FailoverClaimVerifier:
    verifier_id: str
    routes: tuple[ClaimVerifierRoute, ...]
    model_id: str = field(init=False)
    _circuits: tuple[ProviderCircuit, ...] = field(init=False, repr=False)
    _route_counters: dict[str, dict[str, int]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.verifier_id.strip():
            raise ValueError("logical verifier_id must be non-empty")
        if not self.routes:
            raise ValueError("failover verifier requires at least one route")
        route_ids = [f"{route.verifier_id}:{route.model_id}" for route in self.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("failover verifier routes must be unique")
        self.model_id = "failover[" + ",".join(route_ids) + "]"
        self._circuits = tuple(ProviderCircuit(route_id) for route_id in route_ids)
        self._route_counters = {
            route_id: {"calls": 0, "supported": 0, "rejected": 0, "unavailable": 0, "exceptions": 0, "circuit_skips": 0}
            for route_id in route_ids
        }

    @property
    def circuits(self) -> tuple[ProviderCircuit, ...]:
        return self._circuits

    @property
    def route_stats(self) -> dict[str, dict[str, object]]:
        output: dict[str, dict[str, object]] = {}
        for route, circuit in zip(self.routes, self._circuits, strict=True):
            route_id = f"{route.verifier_id}:{route.model_id}"
            output[route_id] = {
                **self._route_counters[route_id],
                "state": circuit.state.value,
                "open_reason": circuit.open_reason.value if circuit.open_reason is not None else None,
            }
        return output

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        attempted = False
        last_error = "insufficient_verification_capacity"
        for route, circuit in zip(self.routes, self._circuits, strict=True):
            route_id = f"{route.verifier_id}:{route.model_id}"
            counters = self._route_counters[route_id]
            if not circuit.allows_call():
                counters["circuit_skips"] += 1
                continue
            attempted = True
            counters["calls"] += 1
            try:
                check = route.verify(
                    check_id=check_id,
                    claim_text=claim_text,
                    evidence_text=evidence_text,
                    evidence_ids=evidence_ids,
                )
            except Exception as exc:
                counters["exceptions"] += 1
                counters["unavailable"] += 1
                last_error = f"verifier_exception:{type(exc).__name__.lower()[:80] or 'unknown'}"
                circuit.record_error_code(last_error)
                continue
            if check.check_id != check_id or check.evidence_ids != evidence_ids:
                raise ValueError("failover route returned mismatched verification identity")
            if check.entailed is not None:
                if check.entailed:
                    counters["supported"] += 1
                else:
                    counters["rejected"] += 1
                circuit.record_success()
                return VerificationCheck(
                    check_id=check_id,
                    verifier_id=self.verifier_id,
                    model_id=check.model_id,
                    evidence_ids=evidence_ids,
                    entailed=check.entailed,
                    zero_cost=True,
                )
            counters["unavailable"] += 1
            last_error = check.error_code or "provider_inconclusive"
            circuit.record_error_code(last_error)

        status = "insufficient_verification_capacity"
        if attempted and last_error:
            status += ":" + last_error.split(":", 1)[0]
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=None,
            error_code=status,
            zero_cost=True,
        )
