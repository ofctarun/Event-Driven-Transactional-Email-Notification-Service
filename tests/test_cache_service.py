import json
import pytest
from api.src.services.cache_service import CacheService
from api.src.models.db_models import NotificationTemplate, UserPreferences

def test_cache_miss_then_hit_for_template(mock_redis, db_session):
    cache = CacheService(redis_client=mock_redis)
    template_id = "order-confirmation"

    # Step 1: Redis should be empty initially
    assert mock_redis.get(f"template:{template_id}") is None

    # Step 2: Fetch template -> Cache Miss -> Queries DB -> Sets Redis
    template_data = cache.get_template(template_id, db=db_session)
    assert template_data is not None
    assert template_data["id"] == template_id
    assert "Order Confirmation" in template_data["name"]

    # Verify that Redis now contains the cached JSON string
    raw_cached = mock_redis.get(f"template:{template_id}")
    assert raw_cached is not None
    cached_dict = json.loads(raw_cached)
    assert cached_dict["id"] == template_id

    # Step 3: Fetch template again with db=None -> Cache Hit from Redis
    cached_hit_data = cache.get_template(template_id, db=None)
    assert cached_hit_data is not None
    assert cached_hit_data["id"] == template_id

def test_cache_miss_then_hit_for_user_preferences(mock_redis, db_session):
    cache = CacheService(redis_client=mock_redis)
    email = "carlos@example.es"

    assert mock_redis.get(f"user_prefs:email:{email}") is None

    # Cache Miss -> Queries DB -> Sets Redis
    prefs = cache.get_user_preferences(email, db=db_session)
    assert prefs["preferred_language"] == "es"
    assert prefs["email_opt_out"] is False

    # Check Redis
    raw_cached = mock_redis.get(f"user_prefs:email:{email}")
    assert raw_cached is not None
    assert json.loads(raw_cached)["preferred_language"] == "es"

    # Cache Hit without DB
    prefs_hit = cache.get_user_preferences(email, db=None)
    assert prefs_hit["preferred_language"] == "es"

def test_cache_invalidation(mock_redis, db_session):
    cache = CacheService(redis_client=mock_redis)
    template_id = "password-reset"

    cache.get_template(template_id, db=db_session)
    assert mock_redis.get(f"template:{template_id}") is not None

    cache.invalidate_template(template_id)
    assert mock_redis.get(f"template:{template_id}") is None
