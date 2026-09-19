import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
import pika
from ..config import settings

logger = logging.getLogger(__name__)

class RabbitMQProducer:
    def __init__(self):
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None

    def _get_connection_params(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
        return pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=300,
            connection_attempts=3,
            retry_delay=2,
        )

    def connect(self) -> None:
        """Establish or verify RabbitMQ connection and durable queue topology."""
        if self._connection and self._connection.is_open and self._channel and self._channel.is_open:
            return

        try:
            params = self._get_connection_params()
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()

            # Declare durable exchange
            self._channel.exchange_declare(
                exchange=settings.RABBITMQ_EXCHANGE,
                exchange_type="direct",
                durable=True,
            )

            # Declare durable queue
            self._channel.queue_declare(
                queue=settings.RABBITMQ_QUEUE,
                durable=True,
                arguments={
                    "x-max-priority": 10,
                }
            )

            # Bind queue to exchange
            self._channel.queue_bind(
                queue=settings.RABBITMQ_QUEUE,
                exchange=settings.RABBITMQ_EXCHANGE,
                routing_key=settings.RABBITMQ_ROUTING_KEY,
            )

            logger.info("RabbitMQ Producer successfully connected and queue declared.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ broker: {e}")
            self._connection = None
            self._channel = None
            raise

    def check_connection(self) -> bool:
        """Check RabbitMQ health status."""
        try:
            params = self._get_connection_params()
            conn = pika.BlockingConnection(params)
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"RabbitMQ healthcheck failed: {e}")
            return False

    def publish_notification(
        self,
        recipient_email: str,
        template_id: str,
        dynamic_data: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Publish a persistent notification message to RabbitMQ.
        
        Returns:
            Tuple[success: bool, notification_id: str, error_message: Optional[str]]
        """
        notification_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        payload = {
            "notification_id": notification_id,
            "recipient_email": recipient_email,
            "template_id": template_id,
            "dynamic_data": dynamic_data,
            "timestamp": timestamp,
        }

        try:
            self.connect()
            message_body = json.dumps(payload)

            # delivery_mode=2 marks message as persistent (written to disk by RabbitMQ)
            properties = pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
                message_id=notification_id,
                timestamp=int(datetime.now(timezone.utc).timestamp()),
            )

            self._channel.basic_publish(
                exchange=settings.RABBITMQ_EXCHANGE,
                routing_key=settings.RABBITMQ_ROUTING_KEY,
                body=message_body.encode("utf-8"),
                properties=properties,
                mandatory=True,
            )

            logger.info(
                f"Published notification event [ID: {notification_id}] "
                f"for {recipient_email} using template '{template_id}'"
            )
            return True, notification_id, None

        except Exception as e:
            logger.error(f"Failed to publish notification event to RabbitMQ: {e}")
            # Reset connection state on error
            self._connection = None
            self._channel = None
            return False, notification_id, str(e)

    def close(self) -> None:
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception as e:
            logger.warning(f"Error closing RabbitMQ connection: {e}")

rabbitmq_producer = RabbitMQProducer()
