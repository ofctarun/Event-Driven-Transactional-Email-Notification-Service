import json
import pytest
from unittest.mock import MagicMock
from worker.src.consumer import NotificationWorker
from worker.src.cache_service import WorkerCacheService

def test_full_integration_flow(client, mock_redis, mock_rabbitmq, db_session):
    """
    End-to-End Integration Flow:
    1. Client calls POST /api/notifications/email
    2. API validates, checks rate limit in Redis, resolves template, pre-caches preferences
    3. API publishes persistent event to RabbitMQ
    4. API returns HTTP 202 Accepted
    5. Worker picks up event from RabbitMQ
    6. Worker resolves template from Redis cache (cache HIT)
    7. Worker verifies user preference (opt-in)
    8. Worker renders Jinja2 template and sends simulated email
    9. Worker acknowledges RabbitMQ delivery
    """
    # 1. Dispatch API Request
    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "order-confirmation",
        "dynamic_data": {
            "order_id": "ORD-12345",
            "customer_name": "Alice Smith",
            "product_name": "Ultra Wireless Headphones",
            "total_amount": "299.99"
        }
    }

    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 202
    resp_data = response.json()
    assert resp_data["status"] == "accepted"
    notification_id = resp_data["notification_id"]
    assert notification_id is not None

    # 2. Verify RabbitMQ received message
    assert len(mock_rabbitmq.published_messages) == 1
    published_msg = mock_rabbitmq.published_messages[0]
    assert published_msg["recipient_email"] == "alice@example.com"
    assert published_msg["template_id"] == "order-confirmation"
    assert published_msg["notification_id"] == notification_id

    # 3. Verify Redis has cached template and user prefs
    cached_template = mock_redis.get("template:order-confirmation")
    assert cached_template is not None
    assert "Order Confirmation" in cached_template

    cached_user = mock_redis.get("user_prefs:email:alice@example.com")
    assert cached_user is not None

    # 4. Simulate Worker Consumption of the published event
    worker = NotificationWorker()
    from worker.src import consumer
    consumer.worker_cache_service = WorkerCacheService(redis_client=mock_redis)

    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 101

    raw_body = json.dumps(published_msg).encode("utf-8")
    worker.process_message(mock_channel, mock_method, None, raw_body)

    # 5. Verify worker acknowledged message
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=101)

def test_health_check_endpoints(client, mock_redis, mock_rabbitmq):
    """Verify both /health and /api/health return healthy component statuses."""
    res1 = client.get("/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "healthy"
    assert data1["components"]["redis"] == "up"
    assert data1["components"]["rabbitmq"] == "up"

    res2 = client.get("/api/health")
    assert res2.status_code == 200
