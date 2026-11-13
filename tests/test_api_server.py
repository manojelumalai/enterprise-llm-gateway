import pytest
from httpx import ASGITransport, AsyncClient

from llm_gateway.api.server import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


@pytest.mark.asyncio
async def test_chat_completions_flow_and_caching():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "How do I optimize RAG retrieval?"}],
            "max_tokens": 150,
        }

        # 1. First call: Cache miss
        res1 = await ac.post("/v1/chat/completions", json=payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["cached"] is False
        assert "choices" in data1

        # 2. Second call: Exact/Semantic Cache hit
        res2 = await ac.post("/v1/chat/completions", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["cached"] is True
        assert data2["usage"]["tokens_saved"] > 0


@pytest.mark.asyncio
async def test_evals_rag_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "query": "What is FAST?",
            "context": (
                "FAST is Fast And Secure Transfers, a Singapore electronic funds transfer service."
            ),
            "response": "FAST is a Singapore funds transfer service.",
        }
        res = await ac.post("/v1/evals/rag", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "composite_score" in data
        assert data["passed"] is True
