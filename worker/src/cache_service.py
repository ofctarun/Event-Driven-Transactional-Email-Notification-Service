import json
import logging
from typing import Optional, Dict, Any
import redis
from .config import worker_settings
from .database import SessionLocal, NotificationTemplate, UserPreferences

logger = logging.getLogger(__name__)

class WorkerCacheService:
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._client = redis_client

    def get_client(self) -> redis.Redis:
        if self._client is None:
            if worker_settings.REDIS_URL:
                self._client = redis.from_url(worker_settings.REDIS_URL, decode_responses=True)
            else:
                self._client = redis.Redis(
                    host=worker_settings.REDIS_HOST,
                    port=worker_settings.REDIS_PORT,
                    db=worker_settings.REDIS_DB,
                    password=worker_settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
        return self._client

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Worker cache lookup: Checks Redis template:<template_id>, falls back to DB.
        """
        cache_key = f"template:{template_id}"
        client = None

        # 1. Try Redis cache
        try:
            client = self.get_client()
            cached = client.get(cache_key)
            if cached:
                logger.info(f"Worker Cache HIT for template '{template_id}'")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Worker Redis cache read error for '{cache_key}': {e}")

        logger.info(f"Worker Cache MISS for template '{template_id}' - querying DB")

        # 2. Database fallback
        db = SessionLocal()
        try:
            template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
            if template:
                data = template.to_dict()
                if client is not None:
                    try:
                        client.set(cache_key, json.dumps(data), ex=worker_settings.TEMPLATE_CACHE_TTL)
                    except Exception as e:
                        logger.warning(f"Worker failed to write template to Redis: {e}")
                return data
            return None
        finally:
            db.close()

    def get_user_preferences(self, email: str) -> Dict[str, Any]:
        """
        Worker cache lookup: Checks Redis user_prefs:email:<email>, falls back to DB.
        """
        cache_key = f"user_prefs:email:{email.lower()}"
        client = None

        # 1. Try Redis cache
        try:
            client = self.get_client()
            cached = client.get(cache_key)
            if cached:
                logger.info(f"Worker Cache HIT for user preferences '{email}'")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Worker Redis cache read error for '{cache_key}': {e}")

        logger.info(f"Worker Cache MISS for user preferences '{email}' - querying DB")

        # 2. Database fallback
        db = SessionLocal()
        try:
            prefs = db.query(UserPreferences).filter(UserPreferences.email == email.lower()).first()
            if prefs:
                data = prefs.to_dict()
                if client is not None:
                    try:
                        client.set(cache_key, json.dumps(data), ex=worker_settings.USER_PREFS_CACHE_TTL)
                    except Exception as e:
                        logger.warning(f"Worker failed to write user prefs to Redis: {e}")
                return data
        finally:
            db.close()

        # Return default preferences if user record doesn't exist
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
                client.set(cache_key, json.dumps(default_prefs), ex=worker_settings.USER_PREFS_CACHE_TTL)
            except Exception as e:
                logger.warning(f"Worker failed to cache default user prefs: {e}")

        return default_prefs

worker_cache_service = WorkerCacheService()
