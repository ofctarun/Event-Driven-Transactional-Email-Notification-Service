import json
import pytest
from unittest.mock import MagicMock
from worker.src.consumer import NotificationWorker
from worker.src.cache_service import WorkerCacheService

def test_worker_respects_opt_out(mock_redis):
    # Setup mock user who opted out
    user_email = "bob.optout@example.com"
    mock_redis.set(
        f"user_prefs:email:{user_email}", 
        json.dumps({
            "user_id": "usr-002",
            "email": user_email,
            "email_opt_out": True,
            "preferred_language": "en"
        })
    )

    worker = NotificationWorker()
    # Inject mock cache
    from worker.src import consumer
    consumer.worker_cache_service = WorkerCacheService(redis_client=mock_redis)

    # Mock channel and delivery method
    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 12345

    payload = {
        "notification_id": "test-uuid-optout",
        "recipient_email": user_email,
        "template_id": "order-confirmation",
        "dynamic_data": {"order_id": "123"}
    }
    body = json.dumps(payload).encode("utf-8")

    # Call process_message
    worker.process_message(mock_channel, mock_method, None, body)

    # Assert that message was acknowledged (without sending email)
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=12345)
