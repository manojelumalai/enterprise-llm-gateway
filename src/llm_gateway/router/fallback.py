"""
Multi-Provider Routing Gateway and Circuit Breaker Fallback Engine.
Provides high-availability inference routing across OpenAI, Anthropic Claude, and Google Gemini.
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ProviderType(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ProviderConfig(BaseModel):
    name: ProviderType
    model: str
    priority: int
    timeout_seconds: float = 3.0
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0


class ProviderStatus:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.consecutive_failures: int = 0
        self.is_healthy: bool = True
        self.tripped_at: float | None = None
        self.total_requests: int = 0
        self.total_latency_ms: float = 0.0

    def record_success(self, latency_ms: float) -> None:
        self.consecutive_failures = 0
        self.is_healthy = True
        self.tripped_at = None
        self.total_requests += 1
        self.total_latency_ms += latency_ms

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_requests += 1
        if self.consecutive_failures >= self.config.failure_threshold:
            self.is_healthy = False
            self.tripped_at = time.time()

    def check_health(self) -> bool:
        if (
            not self.is_healthy
            and self.tripped_at
            and (time.time() - self.tripped_at > self.config.cooldown_seconds)
        ):
            # Half-open state for probing
            self.is_healthy = True
            self.consecutive_failures = 0
        return self.is_healthy

    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency_ms / self.total_requests) if self.total_requests > 0 else 0.0


class MultiProviderRouter:
    """
    Intelligent router with fallback chains and latency-aware failover.

    Provider calls are simulated (see ``_call_provider``): no network request is
    made to OpenAI, Anthropic, or Google. Swap ``_call_provider`` for a real
    SDK/HTTP call (e.g. the OpenAI or Anthropic client) to use this against
    live providers; the circuit breaker, fallback ordering, and health
    tracking above are provider-agnostic and need no changes.
    """

    def __init__(self, providers: list[ProviderConfig] | None = None) -> None:
        default_providers = providers or [
            ProviderConfig(name=ProviderType.OPENAI, model="gpt-4o", priority=1),
            ProviderConfig(name=ProviderType.ANTHROPIC, model="claude-3-5-sonnet", priority=2),
            ProviderConfig(name=ProviderType.GEMINI, model="gemini-1.5-pro", priority=3),
        ]
        # Sort by priority
        self.providers: dict[ProviderType, ProviderStatus] = {
            p.name: ProviderStatus(p) for p in sorted(default_providers, key=lambda x: x.priority)
        }

    async def execute_with_fallback(
        self, prompt: str, system_prompt: str | None = None
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for p_name, provider_status in self.providers.items():
            if not provider_status.check_health():
                continue

            start_time = time.perf_counter()
            try:
                # Execute simulated provider call with timeout
                result = await asyncio.wait_for(
                    self._call_provider(
                        p_name, provider_status.config.model, prompt, system_prompt
                    ),
                    timeout=provider_status.config.timeout_seconds,
                )
                latency = (time.perf_counter() - start_time) * 1000
                provider_status.record_success(latency)
                return {
                    "provider": p_name.value,
                    "model": provider_status.config.model,
                    "content": result,
                    "latency_ms": round(latency, 2),
                    "fallback_triggered": p_name != ProviderType.OPENAI,
                }
            except Exception as exc:
                provider_status.record_failure()
                last_error = exc
                continue

        raise RuntimeError(f"All LLM providers exhausted. Last failure: {last_error}")

    async def _call_provider(
        self, provider: ProviderType, model: str, prompt: str, system_prompt: str | None
    ) -> str:
        # Simulated provider call: no real network/API call is made. Replace this
        # body with a real client call (e.g. `openai.AsyncOpenAI().chat.completions.create(...)`)
        # to route to a live provider; everything else in this class stays the same.
        await asyncio.sleep(0.01)  # Simulate network hop
        return f"[{provider.value} / {model}] Processed query: '{prompt[:50]}...'"

    def get_cluster_status(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": p.config.name.value,
                "model": p.config.model,
                "priority": p.config.priority,
                "healthy": p.check_health(),
                "failures": p.consecutive_failures,
                "avg_latency_ms": round(p.avg_latency_ms, 2),
            }
            for p in self.providers.values()
        ]
