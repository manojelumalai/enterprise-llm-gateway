from llm_gateway.rate_limiter.token_bucket import TokenBucketLimiter


def test_token_bucket_normal_acquisition():
    limiter = TokenBucketLimiter()
    allowed, reason = limiter.acquire("tenant_abc", estimated_tokens=1000)
    assert allowed is True
    assert reason is None


def test_token_bucket_tpm_exhaustion():
    limiter = TokenBucketLimiter()
    limiter.register_tenant("tenant_small", tpm=500, rpm=10)

    # First request consumes 400
    allowed, _ = limiter.acquire("tenant_small", estimated_tokens=400)
    assert allowed is True

    # Second request requires 200 (only 100 left) -> rejected
    allowed, reason = limiter.acquire("tenant_small", estimated_tokens=200)
    assert allowed is False
    assert "TPM quota exceeded" in reason


def test_token_bucket_rpm_exhaustion():
    limiter = TokenBucketLimiter()
    limiter.register_tenant("tenant_rpm", tpm=100000, rpm=1)

    allowed1, _ = limiter.acquire("tenant_rpm", estimated_tokens=10)
    assert allowed1 is True

    allowed2, reason = limiter.acquire("tenant_rpm", estimated_tokens=10)
    assert allowed2 is False
    assert "RPM limit exceeded" in reason
