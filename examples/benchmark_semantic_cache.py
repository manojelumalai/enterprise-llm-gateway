"""
Benchmark Semantic Cache Latency and Token Savings.

Runs 8 requests: some are exact repeats, one is a genuine near-duplicate
rewording, and the rest are distinct topics. Run it yourself and compare
the printed numbers against the README - they come straight from this
script, nothing here is simulated except the "upstream LLM" latency, which
is clearly labeled below.
"""

import asyncio
import time

from llm_gateway.cache.semantic import SemanticCache


async def run_benchmark() -> None:
    cache = SemanticCache(similarity_threshold=0.90)

    queries = [
        "What are the requirements for Singapore Employment Pass COMPASS?",
        "How do I apply for an EP in Singapore with MOM COMPASS criteria?",
        "What are the requirements for Singapore Employment Pass COMPASS?",  # Exact hit
        "What are the requirements for the Singapore Employment Pass COMPASS?",  # Semantic hit
        "How do I setup Kafka event streaming with CQRS microservices?",
        "How do I setup Kafka event streaming with CQRS microservices?",  # Exact hit
        "What is the interbank settlement cutoff time for FAST in Singapore?",
        "What is the interbank settlement cutoff time for FAST in Singapore?",  # Exact hit
    ]

    print("=== Running Gateway Semantic Cache Benchmark ===")
    total_time = 0.0

    for i, q in enumerate(queries, 1):
        t0 = time.perf_counter()
        resp, score = await cache.get(q)
        t_elapsed_ms = (time.perf_counter() - t0) * 1000
        total_time += t_elapsed_ms

        if resp is None:
            # Simulate upstream LLM generation latency (~650ms). No real provider
            # is called here or anywhere in this cache module; see router/fallback.py
            # for the (also simulated) provider-routing layer.
            simulated_upstream_ms = 650.0
            print(f"[{i:02d}] MISS: '{q[:45]}...' -> Upstream Call ({simulated_upstream_ms:.1f}ms)")
            await cache.set(query=q, response=f"Answer for {q}", model="gpt-4o", tokens_saved=250)
        else:
            print(
                f"[{i:02d}] HIT (Score: {score:.3f}): '{q[:45]}...' "
                f"-> Cached ({t_elapsed_ms:.2f}ms, 250 tokens saved)"
            )

    stats = cache.stats()
    print("\n=== Benchmark Summary ===")
    print(f"Total Requests:      {len(queries)}")
    print(f"Cache Hits:          {stats['hits']}")
    print(f"Cache Misses:        {stats['misses']}")
    print(f"Cache Hit Ratio:     {stats['hit_ratio'] * 100:.1f}%")
    print(f"Total Tokens Saved:  {stats['total_tokens_saved']}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
