import json
import logging
from typing import Optional, Dict, Any
import redis
from sqlalchemy.orm import Session
from ..config import settings
from ..models.db_models import NotificationTemplate, UserPreferences

logger = logging.getLogger(__name__)

class CacheService:
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

    def check_connection(self) -> bool:
        try:
            client = self.get_client()
            return client.ping() is True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False

    def get_template(self, template_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch template from Redis cache; on miss, load from DB and cache in Redis.
        Key structure: template:<template_id>
        """
        cache_key = f"template:{template_id}"
        client = None

        # 1. Check Redis Cache
        try:
            client = self.get_client()
            cached_data = client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for template '{template_id}'")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis cache read error for '{cache_key}': {e}")

        logger.info(f"Cache MISS for template '{template_id}' - querying database")

        # 2. Database Fallback
        if db is not None:
            template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
            if template:
                data = template.to_dict()
                # 3. Store in Redis
                if client is not None:
                    try:
                        client.set(cache_key, json.dumps(data), ex=settings.TEMPLATE_CACHE_TTL)
                        logger.info(f"Cached template '{template_id}' with TTL={settings.TEMPLATE_CACHE_TTL}s")
                    except Exception as e:
                        logger.warning(f"Failed to cache template in Redis: {e}")
                return data

        return None

    def get_user_preferences(self, email: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Fetch user preferences from Redis cache; on miss, load from DB and cache in Redis.
        Key structure: user_prefs:email:<email>
        """
        cache_key = f"user_prefs:email:{email.lower()}"
        client = None

        # 1. Check Redis Cache
        try:
            client = self.get_client()
            cached_data = client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for user preferences '{email}'")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis cache read error for '{cache_key}': {e}")

        logger.info(f"Cache MISS for user preferences '{email}' - querying database")

        # 2. Database Fallback
        if db is not None:
            prefs = db.query(UserPreferences).filter(UserPreferences.email == email.lower()).first()
            if prefs:
                data = prefs.to_dict()
                if client is not None:
                    try:
                        client.set(cache_key, json.dumps(data), ex=settings.USER_PREFS_CACHE_TTL)
                        logger.info(f"Cached user preferences for '{email}' with TTL={settings.USER_PREFS_CACHE_TTL}s")
                    except Exception as e:
                        logger.warning(f"Failed to cache user preferences in Redis: {e}")
                return data

        # Default preferences if user is not in database
        default_prefs = {
            "user_id": f"anon-{email.lower()}",
            "email": email.lower(),
            "email_opt_out": False,
            "preferred_language": "en",
            "created_at": None,
            "updated_at": None,
        }
        if client is not None:
            try:
                client.set(cache_key, json.dumps(default_prefs), ex=settings.USER_PREFS_CACHE_TTL)
            except Exception as e:
                logger.warning(f"Failed to cache default preferences in Redis: {e}")

        return default_prefs

    def invalidate_template(self, template_id: str) -> None:
        try:
            client = self.get_client()
            client.delete(f"template:{template_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate template cache: {e}")

    def invalidate_user_preferences(self, email: str) -> None:
        try:
            client = self.get_client()
            client.delete(f"user_prefs:email:{email.lower()}")
        except Exception as e:
            logger.warning(f"Failed to invalidate user preferences cache: {e}")

cache_service = CacheService()
