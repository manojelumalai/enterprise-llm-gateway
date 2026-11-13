# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-13

### Added
- OpenAI-compatible `/v1/chat/completions` endpoint with simulated multi-provider routing.
- Two-tier semantic cache (exact SHA-256 hash + cosine similarity over a deterministic hashed bag-of-words embedding).
- Per-tenant token-bucket rate limiter enforcing RPM/TPM quotas (`/v1/chat/completions`).
- Multi-provider circuit-breaker router with simulated OpenAI/Anthropic/Gemini fallback chain and `/v1/gateway/stats` cluster status.
- Lexical-heuristic RAG Triad evaluator (context relevance, groundedness, answer relevance) via `/v1/evals/rag`.
- `/health` liveness endpoint.
- Dockerfile, docker-compose, CI (lint/typecheck/test matrix/docker build), pre-commit hooks, issue/PR templates, and packaging metadata for open-source release.

[Unreleased]: https://github.com/manojelumalai/enterprise-llm-gateway/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/manojelumalai/enterprise-llm-gateway/releases/tag/v1.0.0
