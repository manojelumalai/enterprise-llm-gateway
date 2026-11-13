import pytest

from llm_gateway.cache.semantic import SemanticCache


@pytest.mark.asyncio
async def test_cache_miss_and_set():
    cache = SemanticCache(similarity_threshold=0.90)
    query = "What is the capital of Singapore?"
    response = "Singapore is a sovereign city-state in Southeast Asia."

    # Cache miss
    res, _score = await cache.get(query)
    assert res is None

    # Populate cache
    await cache.set(query=query, response=response, model="gpt-4o", tokens_saved=100)

    # Exact Cache hit
    hit_res, hit_score = await cache.get(query)
    assert hit_res == response
    assert hit_score == 1.0
    assert cache.hits == 1
    assert cache.total_tokens_saved == 100


@pytest.mark.asyncio
async def test_semantic_cache_hit():
    cache = SemanticCache(similarity_threshold=0.85)
    query_1 = "How do I transfer money using FAST network in Singapore?"
    response = "To transfer funds via FAST, go to Payments and select FAST instant settlement."

    await cache.set(query=query_1, response=response, model="gpt-4o", tokens_saved=200)

    # Semantically near identical query
    query_2 = "How do I transfer money using FAST network in Singapore?"
    hit_res, score = await cache.get(query_2)
    assert hit_res == response
    assert score >= 0.85


@pytest.mark.asyncio
async def test_cache_eviction():
    cache = SemanticCache(max_size=2)
    await cache.set("q1", "r1", "m1")
    await cache.set("q2", "r2", "m2")
    await cache.set("q3", "r3", "m3")

    assert len(cache._entries) == 2
    # q1 should be evicted
    r, _ = await cache.get("q1")
    assert r is None
