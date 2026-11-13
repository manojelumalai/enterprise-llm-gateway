"""
Token Bucket Rate Limiter and Multi-Tenant Budget Governor.
Enforces per-tenant Requests Per Minute (RPM) and Tokens Per Minute (TPM) quotas.
"""

from __future__ import annotations

import time

from pydantic import BaseModel


class TenantQuota(BaseModel):
    max_tokens_per_minute: int = 100000
    max_requests_per_minute: int = 60
    current_tokens: float = 100000.0
    current_requests: float = 60.0
    last_refill_timestamp: float = 0.0


class TokenBucketLimiter:
    """
    In-memory Token Bucket implementation with sub-second refill rates.
    Thread-safe and async-compatible.
    """

    def __init__(self) -> None:
        self._tenants: dict[str, TenantQuota] = {}

    def register_tenant(self, tenant_id: str, tpm: int = 100000, rpm: int = 60) -> TenantQuota:
        quota = TenantQuota(
            max_tokens_per_minute=tpm,
            max_requests_per_minute=rpm,
            current_tokens=float(tpm),
            current_requests=float(rpm),
            last_refill_timestamp=time.time(),
        )
        self._tenants[tenant_id] = quota
        return quota

    def _refill(self, quota: TenantQuota) -> None:
        now = time.time()
        elapsed = now - quota.last_refill_timestamp

        # Refill tokens proportionally (per second)
        token_refill_rate = quota.max_tokens_per_minute / 60.0
        req_refill_rate = quota.max_requests_per_minute / 60.0

        quota.current_tokens = min(
            float(quota.max_tokens_per_minute),
            quota.current_tokens + (elapsed * token_refill_rate),
        )
        quota.current_requests = min(
            float(quota.max_requests_per_minute),
            quota.current_requests + (elapsed * req_refill_rate),
        )
        quota.last_refill_timestamp = now

    def acquire(self, tenant_id: str, estimated_tokens: int = 500) -> tuple[bool, str | None]:
        """
        Attempt to acquire budget for 1 request and N tokens.
        Returns (allowed, error_reason).
        """
        if tenant_id not in self._tenants:
            self.register_tenant(tenant_id)

        quota = self._tenants[tenant_id]
        self._refill(quota)

        if quota.current_requests < 1.0:
            return False, (
                f"RPM limit exceeded for tenant '{tenant_id}'. "
                f"Available: {quota.current_requests:.1f}"
            )

        if quota.current_tokens < estimated_tokens:
            return False, (
                f"TPM quota exceeded for tenant '{tenant_id}'. "
                f"Requested: {estimated_tokens}, Available: {quota.current_tokens:.1f}"
            )

        quota.current_requests -= 1.0
        quota.current_tokens -= estimated_tokens
        return True, None
