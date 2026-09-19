import sys
import os

# Set environment variables for testing before any application imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "test"
os.environ["REDIS_HOST"] = "localhost"
os.environ["RABBITMQ_HOST"] = "localhost"

from typing import Dict, Any, Optional

# Add repo root to Python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.src.database import Base, get_db
from api.src.models.db_models import NotificationTemplate, UserPreferences
from api.src.main import app
from api.src.services.rate_limiter import RedisRateLimiter
from api.src.services.cache_service import CacheService
from api.src.services.rabbitmq_producer import RabbitMQProducer

class MockRedisPipeline:
    def __init__(self, mock_redis):
        self.mock_redis = mock_redis
        self.commands = []

    def incr(self, key):
        self.commands.append(("incr", key))
        return self

    def ttl(self, key):
        self.commands.append(("ttl", key))
        return self

    def execute(self):
        results = []
        for cmd, key in self.commands:
            if cmd == "incr":
                val = self.mock_redis.incr(key)
                results.append(val)
            elif cmd == "ttl":
                results.append(self.mock_redis.ttl(key))
        self.commands = []
        return results

class MockRedisClient:
    """Thread-safe in-memory Redis simulator for test isolation."""
    def __init__(self):
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self.store[key] = str(value)
        if ex is not None:
            self.ttls[key] = ex
        return True

    def delete(self, key: str) -> int:
        deleted = 1 if key in self.store else 0
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return deleted

    def incr(self, key: str) -> int:
        val = int(self.store.get(key, 0)) + 1
        self.store[key] = str(val)
        return val

    def ttl(self, key: str) -> int:
        if key not in self.store:
            return -2
        return self.ttls.get(key, -1)

    def expire(self, key: str, seconds: int) -> bool:
        if key in self.store:
            self.ttls[key] = seconds
            return True
        return False

    def ping(self) -> bool:
        return True

    def pipeline(self):
        return MockRedisPipeline(self)

    def flushall(self):
        self.store.clear()
        self.ttls.clear()

class MockRabbitMQProducer:
    """Mock RabbitMQ producer capturing published events."""
    def __init__(self):
        self.published_messages = []
        self.is_healthy = True

    def check_connection(self) -> bool:
        return self.is_healthy

    def publish_notification(self, recipient_email: str, template_id: str, dynamic_data: Dict[str, Any]):
        if not self.is_healthy:
            return False, "", "RabbitMQ connection refused"
        import uuid
        notification_id = str(uuid.uuid4())
        message = {
            "notification_id": notification_id,
            "recipient_email": recipient_email,
            "template_id": template_id,
            "dynamic_data": dynamic_data,
        }
        self.published_messages.append(message)
        return True, notification_id, None

    def close(self):
        pass

# In-Memory SQLite Setup with StaticPool
from sqlalchemy.pool import StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def setup_database_schema():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session(setup_database_schema):
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Seed initial test data identical to init-db.sql
    templates = [
        NotificationTemplate(
            id="order-confirmation",
            name="Order Confirmation",
            subject_template="Order Confirmation - {{ order_id }}",
            body_template="Hello {{ customer_name }},\n\nThank you for your order #{{ order_id }} of {{ product_name }}. Total: ${{ total_amount }}.",
            language="en"
        ),
        NotificationTemplate(
            id="password-reset",
            name="Password Reset Request",
            subject_template="Password Reset Request for {{ user_name }}",
            body_template="Hello {{ user_name }}, reset password here: {{ reset_link }}. Expires in {{ expiry_minutes }}m.",
            language="en"
        ),
        NotificationTemplate(
            id="account-alert",
            name="Security Account Alert",
            subject_template="Security Alert: New Sign-in from {{ device }}",
            body_template="Dear {{ user_name }}, sign-in from {{ device }} in {{ location }} at {{ login_time }}.",
            language="en"
        )
    ]
    for t in templates:
        db.add(t)

    users = [
        UserPreferences(user_id="usr-001", email="alice@example.com", email_opt_out=False, preferred_language="en"),
        UserPreferences(user_id="usr-002", email="bob.optout@example.com", email_opt_out=True, preferred_language="en"),
        UserPreferences(user_id="usr-003", email="carlos@example.es", email_opt_out=False, preferred_language="es"),
        UserPreferences(user_id="usr-004", email="diana@example.fr", email_opt_out=False, preferred_language="fr"),
        UserPreferences(user_id="usr-005", email="evan@example.com", email_opt_out=False, preferred_language="en"),
    ]
    for u in users:
        db.add(u)
    db.commit()

    yield db
    db.close()

@pytest.fixture
def mock_redis():
    return MockRedisClient()

@pytest.fixture
def mock_rabbitmq():
    return MockRabbitMQProducer()

@pytest.fixture
def client(db_session, mock_redis, mock_rabbitmq):
    # Override dependencies
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Inject mock Redis into rate_limiter and cache_service
    import api.src.database
    api.src.database.engine = test_engine
    from api.src.services.rate_limiter import rate_limiter
    from api.src.services.cache_service import cache_service
    from api.src.routes import notifications, health

    rate_limiter._client = mock_redis
    cache_service._client = mock_redis
    notifications.rabbitmq_producer = mock_rabbitmq
    health.rabbitmq_producer = mock_rabbitmq

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
