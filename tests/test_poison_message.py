import json
import pytest
from unittest.mock import MagicMock
from worker.src.consumer import NotificationWorker
from worker.src.cache_service import WorkerCacheService

def test_worker_poison_corrupted_json(mock_redis):
    """Test that malformed JSON is caught, logged, and acknowledged without re-queueing."""
    worker = NotificationWorker()
    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 9999

    bad_body = b"NOT_A_VALID_JSON{{"
    worker.process_message(mock_channel, mock_method, None, bad_body)

    # Must acknowledge to prevent poison loop
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=9999)

def test_worker_poison_missing_template(mock_redis):
    """Test that missing template logs error and safely acks."""
    worker = NotificationWorker()
    from worker.src import consumer
    consumer.worker_cache_service = WorkerCacheService(redis_client=mock_redis)

    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 8888

    payload = {
        "notification_id": "test-uuid-notemplate",
        "recipient_email": "alice@example.com",
        "template_id": "ghost-template-does-not-exist",
        "dynamic_data": {}
    }
    body = json.dumps(payload).encode("utf-8")

    worker.process_message(mock_channel, mock_method, None, body)
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=8888)
