import pytest

from llm_gateway.router.fallback import MultiProviderRouter, ProviderType


@pytest.mark.asyncio
async def test_router_primary_success():
    router = MultiProviderRouter()
    res = await router.execute_with_fallback("Hello World")
    assert res["provider"] == ProviderType.OPENAI.value
    assert res["fallback_triggered"] is False
    assert res["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_router_fallback_on_primary_failure():
    router = MultiProviderRouter()

    # Simulate failure on OpenAI
    openai_status = router.providers[ProviderType.OPENAI]
    openai_status.is_healthy = False
    openai_status.tripped_at = 9999999999.0  # Far in future

    res = await router.execute_with_fallback("Hello fallback")
    assert res["provider"] == ProviderType.ANTHROPIC.value
    assert res["fallback_triggered"] is True


@pytest.mark.asyncio
async def test_cluster_status():
    router = MultiProviderRouter()
    status_list = router.get_cluster_status()
    assert len(status_list) == 3
    assert status_list[0]["provider"] == "openai"
    assert status_list[0]["healthy"] is True
