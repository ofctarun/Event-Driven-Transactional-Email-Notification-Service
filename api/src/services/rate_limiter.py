import logging
from typing import Tuple, Optional
import redis
from ..config import settings

logger = logging.getLogger(__name__)

class RedisRateLimiter:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._client = redis_client

    def get_client(self) -> redis.Redis:
        if self._client is None:
            if settings.REDIS_URL:
                self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            else:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
        return self._client

    def is_rate_limited(
        self, 
        client_ip: str, 
        limit: Optional[int] = None, 
        window_seconds: int = 60
    ) -> Tuple[bool, int, int]:
        """
        Check and record rate limiting for a client IP.
        
        Returns:
            Tuple[is_allowed: bool, current_count: int, retry_after_seconds: int]
        """
        effective_limit = limit if limit is not None else settings.RATE_LIMIT_PER_MINUTE
        key = f"rate_limit:ip:{client_ip}"
        
        try:
            client = self.get_client()
            pipeline = client.pipeline()
            pipeline.incr(key)
            pipeline.ttl(key)
            results = pipeline.execute()
            
            current_count = results[0]
            ttl = results[1]
            
            # If key is newly created or has no TTL, set expiration
            if ttl == -1 or ttl is None:
                client.expire(key, window_seconds)
                ttl = window_seconds
            elif ttl == -2:
                # Key already expired
                ttl = window_seconds

            if current_count > effective_limit:
                retry_after = max(ttl, 1)
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip}. "
                    f"Count: {current_count}/{effective_limit}, Retry-After: {retry_after}s"
                )
                return False, current_count, retry_after

            return True, current_count, 0

        except redis.RedisError as e:
            # High availability fallback: log warning and fail-open if Redis is down
            logger.error(f"Redis error during rate limit check for {client_ip}: {e}")
            return True, 1, 0

rate_limiter = RedisRateLimiter()
