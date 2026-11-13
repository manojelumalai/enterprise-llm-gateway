# Enterprise LLM Routing Gateway ⚡🛡️

[![CI](https://github.com/manojelumalai/enterprise-llm-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/manojelumalai/enterprise-llm-gateway/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-teal.svg)](https://fastapi.tiangolo.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy: checked](https://img.shields.io/badge/mypy-checked-blue.svg)](https://mypy-lang.org/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://www.conventionalcommits.org/)

A reference implementation of an **LLM Routing Gateway**: an OpenAI-compatible FastAPI
server with multi-tier **semantic caching**, multi-provider **circuit-breaker failover**,
per-tenant **token-bucket budgeting**, and an automated **RAG Triad evaluator**.

This is a design/portfolio project, not a deployed production system. The provider calls,
the embedding model, and the eval judge are all simulated or heuristic — see
[Design notes / limitations](#design-notes--limitations) below for exactly what that means
and how to swap in real implementations.

---

## 🏛️ Architecture & Request Flow

```
                      +-----------------------------+
                      |   Client / Application SDK  |
                      +--------------+--------------+
                                     |  OpenAI-compatible /v1/chat/completions
                                     v
+--------------------------------------------------------------------------+
|                     FastAPI LLM Routing Gateway                          |
|                                                                          |
|  1. Token Bucket Rate Limiter & Budget Governor (Per-Tenant TPM / RPM)   |
|                                    |                                     |
|                                    v                                     |
|  2. Multi-Tier Semantic Cache                                            |
|     - Tier 1: Exact Hash (O(1))                                          |
|     - Tier 2: Vector Embedding Cosine Similarity (>= 0.90 threshold)     |
|             |                                                            |
|             +-------- [ Cache Hit ] --------------------------------->  | Return
|             |                                                            |
|             v [ Cache Miss ]                                             |
|  3. Multi-Provider Router & Circuit Breaker Failover Chain (simulated)   |
|     +-------------------+    +--------------------+    +---------------+ |
|     | Primary: OpenAI   | -> | Secondary: Claude  | -> | Fallback:     | |
|     | (gpt-4o)          |    | (claude-3-5-sonnet)|    | (gemini-1.5)  | |
|     +-------------------+    +--------------------+    +---------------+ |
|                                    |                                     |
|                                    v                                     |
|  4. Semantic Cache Ingestion & Telemetry Metrics                         |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                    RAG Triad Offline & CI Evaluation (lexical heuristic) |
|                                                                          |
|   [Context Relevance]        [Groundedness / Faithfulness]    [Answer]   |
+--------------------------------------------------------------------------+
```

---

## 📊 Semantic Cache Benchmark

[`examples/benchmark_semantic_cache.py`](examples/benchmark_semantic_cache.py) sends 8
requests through `SemanticCache` directly (no HTTP, no provider simulation) to show the
exact-hash and cosine-similarity tiers working: 4 exact repeats/near-duplicates hit, 4
distinct topics miss. Run it yourself:

```bash
uv run python examples/benchmark_semantic_cache.py
```

Real output from that command:

```
=== Running Gateway Semantic Cache Benchmark ===
[01] MISS: 'What are the requirements for Singapore Emplo...' -> Upstream Call (650.0ms)
[02] MISS: 'How do I apply for an EP in Singapore with MO...' -> Upstream Call (650.0ms)
[03] HIT (Score: 1.000): 'What are the requirements for Singapore Emplo...' -> Cached (0.00ms, 250 tokens saved)
[04] HIT (Score: 0.992): 'What are the requirements for the Singapore E...' -> Cached (0.04ms, 250 tokens saved)
[05] MISS: 'How do I setup Kafka event streaming with CQR...' -> Upstream Call (650.0ms)
[06] HIT (Score: 1.000): 'How do I setup Kafka event streaming with CQR...' -> Cached (0.00ms, 250 tokens saved)
[07] MISS: 'What is the interbank settlement cutoff time ...' -> Upstream Call (650.0ms)
[08] HIT (Score: 1.000): 'What is the interbank settlement cutoff time ...' -> Cached (0.00ms, 250 tokens saved)

=== Benchmark Summary ===
Total Requests:      8
Cache Hits:          4
Cache Misses:        4
Cache Hit Ratio:     50.0%
Total Tokens Saved:  1000
```

The `650.0ms` "Upstream Call" figure is a hardcoded placeholder printed on a miss, not a
measurement — there is no real upstream call in this script. The hit/miss outcomes and
similarity scores above are real, measured values from `SemanticCache`'s cosine-similarity
comparison over the deterministic hashed embeddings described below.

---

## ✨ Key Features

1. **Multi-Tier Semantic Vector Caching:**
   - Exact SHA-256 hash lookup, then cosine similarity against an in-memory vector index.
   - Prompts with similarity $\ge 0.90$ are served from cache, skipping model generation.

2. **Circuit Breaker Failover (simulated providers):**
   - Tracks consecutive failures per provider and trips/half-opens a circuit breaker.
   - On a tripped primary, falls through the configured provider chain (OpenAI → Anthropic → Gemini by default). No real network calls are made to any of these providers — see [Design notes](#design-notes--limitations).

3. **Multi-Tenant Token-Bucket Governor:**
   - Enforces per-tenant Requests Per Minute (RPM) and Tokens Per Minute (TPM) limits with continuous refill.

4. **Automated RAG Triad Evaluator (lexical heuristic):**
   - **Context Relevance:** query-token coverage in retrieved context.
   - **Groundedness / Faithfulness:** response-token coverage in context (flags unsupported claims by word overlap).
   - **Answer Relevance:** query-token coverage in the response.

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/manojelumalai/enterprise-llm-gateway.git
cd enterprise-llm-gateway

make install   # uv sync --all-extras
```

### 2. Run checks (lint, format check, type check, tests + coverage)

```bash
make check
```

### 3. Launch the gateway server

```bash
make run   # uvicorn llm_gateway.api.server:app on :8080
```

---

## 📡 API Usage Examples

All responses below are real output, captured with `httpx.AsyncClient` against the live
FastAPI app (see `tests/test_api_server.py` for the equivalent assertions).

### 1. OpenAI-Compatible Chat Completion

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: tenant_corp_01" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "How do I configure cross-border multi-currency accounts?"}
    ],
    "max_tokens": 150
  }'
```

**First request (cache miss, routed to the simulated "openai" provider):**
```json
{
  "id": "chatcmpl-1d9393f06d95",
  "object": "chat.completion",
  "created": 1794538821,
  "model": "gpt-4o",
  "cached": false,
  "provider": "openai",
  "fallback_triggered": false,
  "latency_ms": 11.38,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "[openai / gpt-4o] Processed query: 'How do I configure cross-border multi-currency acc...'"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 7,
    "completion_tokens": 12,
    "total_tokens": 19
  }
}
```

**Second identical request (exact-hash cache hit):**
```json
{
  "id": "chatcmpl-d3e27b128e53",
  "object": "chat.completion",
  "created": 1794538821,
  "model": "gpt-4o-cached",
  "cached": true,
  "similarity_score": 1.0,
  "latency_ms": 0.02,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "[openai / gpt-4o] Processed query: 'How do I configure cross-border multi-currency acc...'"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "tokens_saved": 150
  }
}
```

### 2. Run Automated RAG Triad Evaluation

```bash
curl -X POST http://localhost:8080/v1/evals/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the maximum transfer limit for FAST in Singapore?",
    "context": "FAST allows real-time interbank fund transfers in Singapore with a maximum limit of 200,000 SGD per transaction.",
    "response": "The maximum transfer limit for FAST transactions in Singapore is 200,000 SGD."
  }'
```

**Evaluation verdict (real output):**
```json
{
  "context_relevance": 0.8,
  "groundedness": 0.778,
  "answer_relevance": 1.0,
  "composite_score": 0.851,
  "passed": true,
  "details": {
    "context_relevance_notes": "Query terms matched: 80.0%",
    "groundedness_notes": "Grounded response terms: 77.8%",
    "answer_relevance_notes": "Intent coverage: 100.0%"
  }
}
```

### 3. Gateway Stats

```bash
curl http://localhost:8080/v1/gateway/stats
```
Returns `cache` stats (hits/misses/hit_ratio/tokens_saved) and `cluster` status (per-provider health, failure count, average latency) from the two requests above.

---

## 🧭 Design notes / limitations

This project demonstrates the *routing, caching, rate-limiting, and evaluation logic*
around an LLM gateway. The following pieces are intentionally simplified so the whole
thing runs with no API keys and no network access — each is pluggable:

- **Provider calls are simulated** (`src/llm_gateway/router/fallback.py`,
  `MultiProviderRouter._call_provider`). It sleeps 10ms and returns a templated string;
  it never calls OpenAI, Anthropic, or Gemini. Swap its body for a real client call (e.g.
  `openai.AsyncOpenAI().chat.completions.create(...)`) to route to live providers — the
  circuit breaker, fallback ordering, and health tracking need no changes.

- **Embeddings are a deterministic hashed bag-of-words**, not a real embedding model
  (`src/llm_gateway/cache/semantic.py`, `_generate_deterministic_embedding`). Each word
  hashes into one of 128 buckets, weighted by position, then L2-normalized. It only
  detects shared-word overlap, not synonyms or paraphrase. Pass a real embedding (e.g.
  from `text-embedding-3-small` or a local sentence-transformers model) via the
  `embedding` argument of `SemanticCache.get`/`.set` to use a real model instead.

- **The RAG Triad evaluator is a lexical heuristic**, not an LLM judge
  (`src/llm_gateway/evals/triad.py`). All three metrics are token-set intersections. It's
  fast and dependency-free for CI smoke tests, but cannot detect a paraphrased grounded
  claim or a hallucination that happens to reuse context words. To use a real judge,
  replace the three `evaluate_*` methods with calls to an LLM scoring rubric (ask the
  model to rate 0–1 per dimension) and keep `evaluate()`'s composite-score/threshold logic
  as-is.

None of the numbers above are production benchmarks — they are outputs of the commands
shown, which you can re-run yourself.

---

## 🛠️ Project Structure

```
enterprise-llm-gateway/
├── src/llm_gateway/
│   ├── cache/
│   │   └── semantic.py         # Exact-hash + cosine-similarity cache (hashed embeddings)
│   ├── router/
│   │   └── fallback.py         # Circuit-breaker failover (simulated provider calls)
│   ├── rate_limiter/
│   │   └── token_bucket.py     # Token bucket RPM/TPM governor
│   ├── evals/
│   │   └── triad.py            # RAG Triad lexical-heuristic evaluator
│   └── api/
│       └── server.py           # FastAPI OpenAI-compatible REST server
├── tests/                      # Pytest suite (see `make test` for coverage)
├── examples/
│   └── benchmark_semantic_cache.py
├── Dockerfile
└── docker-compose.yml
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, commit conventions, and the
PR process. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT License — see [LICENSE](LICENSE). Author: **Manoj Elumalai** ([LinkedIn](https://www.linkedin.com/in/manojelumalai)).
