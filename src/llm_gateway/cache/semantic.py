"""
Semantic Cache Engine: Vector Similarity Caching for LLM Queries.
Cuts inference latency and operational spend by serving cached responses for similar prompts.
"""

from __future__ import annotations

import hashlib
import time

import numpy as np
from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    query_text: str
    embedding: list[float]
    response_text: str
    model: str
    tokens_saved: int
    created_at: float = Field(default_factory=time.time)


class SemanticCache:
    """
    In-memory vector similarity cache for high-throughput LLM workloads.
    Uses cosine similarity metric with configurable similarity threshold.
    """

    def __init__(self, similarity_threshold: float = 0.90, max_size: int = 10000) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self._entries: list[CacheEntry] = []
        self._exact_hash_index: dict[str, CacheEntry] = {}

        # Telemetry metrics
        self.hits: int = 0
        self.misses: int = 0
        self.total_tokens_saved: int = 0

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _generate_deterministic_embedding(self, text: str, dim: int = 128) -> list[float]:
        """
        Deterministic hashed bag-of-words embedding: each word is hashed into one
        of `dim` buckets and weighted by its position, then L2-normalized. This is
        a local, dependency-free stand-in for a real embedding model, so it only
        captures shared-word overlap (it has no notion of synonyms or meaning).
        To use a real embedding, pass a pre-computed vector via the `embedding`
        argument of `get`/`set` (e.g. from OpenAI's `text-embedding-3-small` or a
        local sentence-transformers model) instead of relying on this method.
        """
        tokens = text.lower().split()
        vec = np.zeros(dim, dtype=np.float32)
        for i, token in enumerate(tokens):
            idx = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim
            vec[idx] += 1.0 / (i + 1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def get(
        self, query: str, embedding: list[float] | None = None
    ) -> tuple[str | None, float]:
        """
        Lookup response by exact hash first (O(1)), then vector cosine similarity (O(N)).
        Returns (response_text, similarity_score).
        """
        h = self._hash_text(query)

        # 1. Exact match tier (0ms latency)
        if h in self._exact_hash_index:
            self.hits += 1
            entry = self._exact_hash_index[h]
            self.total_tokens_saved += entry.tokens_saved
            return entry.response_text, 1.0

        if not self._entries:
            self.misses += 1
            return None, 0.0

        # 2. Semantic vector search tier
        default_emb = self._generate_deterministic_embedding(query)
        query_emb = np.array(embedding or default_emb, dtype=np.float32)

        best_score = -1.0
        best_entry: CacheEntry | None = None

        for entry in self._entries:
            entry_emb = np.array(entry.embedding, dtype=np.float32)
            score = self._cosine_similarity(query_emb, entry_emb)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self.similarity_threshold and best_entry is not None:
            self.hits += 1
            self.total_tokens_saved += best_entry.tokens_saved
            return best_entry.response_text, best_score

        self.misses += 1
        return None, best_score

    async def set(
        self,
        query: str,
        response: str,
        model: str,
        tokens_saved: int = 150,
        embedding: list[float] | None = None,
    ) -> None:
        emb = embedding or self._generate_deterministic_embedding(query)
        entry = CacheEntry(
            query_text=query,
            embedding=emb,
            response_text=response,
            model=model,
            tokens_saved=tokens_saved,
        )

        h = self._hash_text(query)
        self._exact_hash_index[h] = entry
        self._entries.append(entry)

        # Evict oldest entry if size exceeded
        if len(self._entries) > self.max_size:
            evicted = self._entries.pop(0)
            self._exact_hash_index.pop(self._hash_text(evicted.query_text), None)

    def stats(self) -> dict[str, float]:
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(hit_ratio, 4),
            "total_tokens_saved": self.total_tokens_saved,
            "cached_entries_count": len(self._entries),
        }
