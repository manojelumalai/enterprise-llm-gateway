"""
High-Concurrency FastAPI LLM Gateway Server.
OpenAI-compatible /v1/chat/completions endpoint with integrated semantic caching,
token-bucket rate limiting, multi-provider failover, and automated RAG evaluation.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llm_gateway.cache.semantic import SemanticCache
from llm_gateway.evals.triad import EvaluationResult, RAGTriadEvaluator
from llm_gateway.rate_limiter.token_bucket import TokenBucketLimiter
from llm_gateway.router.fallback import MultiProviderRouter

app = FastAPI(
    title="Enterprise LLM Routing Gateway",
    version="1.0.0",
    description=(
        "High-concurrency LLM routing with semantic caching, token budgeting, and RAG evals"
    ),
)

# CORS origins are opt-in via env var; wildcard "*" is never combined with
# allow_credentials=True (browsers reject that combination and it defeats the
# purpose of credentialed CORS). Default is no cross-origin access.
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=bool(_cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Gateway Subsystems
cache = SemanticCache(similarity_threshold=0.90)
router = MultiProviderRouter()
limiter = TokenBucketLimiter()
evaluator = RAGTriadEvaluator(pass_threshold=0.80)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 500


class RAGEvalRequest(BaseModel):
    query: str
    context: str
    response: str


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "HEALTHY", "version": "1.0.0"}


@app.get("/v1/gateway/stats")
async def gateway_stats() -> dict[str, Any]:
    return {"cache": cache.stats(), "cluster": router.get_cluster_status()}


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    x_tenant_id: str = Header(default="default_tenant"),
) -> dict[str, Any]:
    start_time = time.perf_counter()
    user_query = req.messages[-1].content if req.messages else ""

    # 1. Check Rate Limiter & Token Budget
    allowed, reason = limiter.acquire(x_tenant_id, estimated_tokens=req.max_tokens)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=reason)

    # 2. Check Multi-Tier Semantic Cache
    cached_response, similarity = await cache.get(user_query)
    if cached_response is not None:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": f"{req.model}-cached",
            "cached": True,
            "similarity_score": round(similarity, 4),
            "latency_ms": round(elapsed_ms, 2),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": cached_response},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "tokens_saved": 150,
            },
        }

    # 3. Cache Miss: Route across providers with fallback
    try:
        route_result = await router.execute_with_fallback(prompt=user_query)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All upstream LLM providers failed: {exc}",
        ) from exc

    # 4. Asynchronously store in semantic cache
    await cache.set(
        query=user_query,
        response=route_result["content"],
        model=route_result["model"],
        tokens_saved=req.max_tokens,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": route_result["model"],
        "cached": False,
        "provider": route_result["provider"],
        "fallback_triggered": route_result["fallback_triggered"],
        "latency_ms": round(elapsed_ms, 2),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": route_result["content"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_query.split()),
            "completion_tokens": len(route_result["content"].split()),
            "total_tokens": len(user_query.split()) + len(route_result["content"].split()),
        },
    }


@app.post("/v1/evals/rag", response_model=EvaluationResult)
async def evaluate_rag(req: RAGEvalRequest) -> EvaluationResult:
    return evaluator.evaluate(query=req.query, context=req.context, response=req.response)
