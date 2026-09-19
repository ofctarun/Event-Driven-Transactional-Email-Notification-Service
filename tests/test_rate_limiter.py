import pytest
from api.src.services.rate_limiter import RedisRateLimiter

def test_rate_limiter_within_limit(mock_redis):
    limiter = RedisRateLimiter(redis_client=mock_redis)
    client_ip = "192.168.1.50"

    # Limit = 5 requests
    for i in range(1, 6):
        allowed, count, retry_after = limiter.is_rate_limited(client_ip, limit=5, window_seconds=60)
        assert allowed is True
        assert count == i
        assert retry_after == 0

def test_rate_limiter_exceeds_limit(mock_redis):
    limiter = RedisRateLimiter(redis_client=mock_redis)
    client_ip = "192.168.1.51"

    # Fill to limit of 3
    for _ in range(3):
        allowed, _, _ = limiter.is_rate_limited(client_ip, limit=3, window_seconds=60)
        assert allowed is True

    # 4th request must be rejected
    allowed, count, retry_after = limiter.is_rate_limited(client_ip, limit=3, window_seconds=60)
    assert allowed is False
    assert count == 4
    assert retry_after > 0

def test_api_rate_limiting_returns_429(client, mock_redis):
    """Test that FastAPI returns 429 Too Many Requests when limit is exceeded."""
    from api.src.config import settings
    original_limit = settings.RATE_LIMIT_PER_MINUTE
    settings.RATE_LIMIT_PER_MINUTE = 2

    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "order-confirmation",
        "dynamic_data": {"order_id": "1001"}
    }

    try:
        # Request 1: OK
        res1 = client.post("/api/notifications/email", json=payload)
        assert res1.status_code == 202

        # Request 2: OK
        res2 = client.post("/api/notifications/email", json=payload)
        assert res2.status_code == 202

        # Request 3: 429 Too Many Requests
        res3 = client.post("/api/notifications/email", json=payload)
        assert res3.status_code == 429
        assert "Rate limit exceeded" in res3.json()["detail"]
        assert "Retry-After" in res3.headers
    finally:
        settings.RATE_LIMIT_PER_MINUTE = original_limit
