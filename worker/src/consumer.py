import json
import logging
import os
import signal
import sys
import time
from typing import Optional
import pika

from .config import worker_settings
from .cache_service import worker_cache_service
from .email_service import email_service

logging.basicConfig(
    level=getattr(logging, worker_settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s"
)
logger = logging.getLogger("worker_consumer")

class NotificationWorker:
    def __init__(self):
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._is_running: bool = False
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Gracefully stopping worker...")
        self._is_running = False
        if self._channel and self._channel.is_open:
            try:
                self._channel.stop_consuming()
            except Exception as e:
                logger.warning(f"Error stopping consumption: {e}")
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
        sys.exit(0)

    def _touch_heartbeat(self):
        try:
            hb_path = worker_settings.HEARTBEAT_FILE
            os.makedirs(os.path.dirname(hb_path), exist_ok=True)
            with open(hb_path, "w") as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.debug(f"Heartbeat write note: {e}")

    def _connect(self):
        credentials = pika.PlainCredentials(
            worker_settings.RABBITMQ_USER, 
            worker_settings.RABBITMQ_PASSWORD
        )
        params = pika.ConnectionParameters(
            host=worker_settings.RABBITMQ_HOST,
            port=worker_settings.RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=300,
        )

        retry_count = 0
        max_retries = 30
        while self._is_running and retry_count < max_retries:
            try:
                logger.info(f"Connecting to RabbitMQ at {worker_settings.RABBITMQ_HOST}:{worker_settings.RABBITMQ_PORT}...")
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()

                # Ensure queue topology matches API producer
                self._channel.exchange_declare(
                    exchange=worker_settings.RABBITMQ_EXCHANGE,
                    exchange_type="direct",
                    durable=True,
                )
                self._channel.queue_declare(
                    queue=worker_settings.RABBITMQ_QUEUE,
                    durable=True,
                    arguments={"x-max-priority": 10}
                )
                self._channel.queue_bind(
                    queue=worker_settings.RABBITMQ_QUEUE,
                    exchange=worker_settings.RABBITMQ_EXCHANGE,
                    routing_key=worker_settings.RABBITMQ_ROUTING_KEY,
                )

                # Set prefetch count for fair dispatching
                self._channel.basic_qos(prefetch_count=worker_settings.RABBITMQ_PREFETCH_COUNT)
                logger.info("Successfully connected to RabbitMQ and configured queue binding.")
                return
            except Exception as e:
                retry_count += 1
                logger.warning(f"RabbitMQ connection failed ({retry_count}/{max_retries}): {e}. Retrying in 3s...")
                time.sleep(3)

        if not self._is_running:
            sys.exit(0)
        logger.error("Could not connect to RabbitMQ broker after multiple retries.")
        sys.exit(1)

    def process_message(self, ch, method, properties, body):
        """
        Main message processing pipeline.
        Guarantees message acknowledgment on both success and poison errors.
        """
        self._touch_heartbeat()
        delivery_tag = method.delivery_tag
        notification_id = "unknown"

        try:
            # 1. Parse JSON payload
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception as parse_err:
                logger.error(f"[POISON MESSAGE] Failed to parse JSON payload: {parse_err}. Acking to avoid queue blockage.")
                ch.basic_ack(delivery_tag=delivery_tag)
                return

            notification_id = payload.get("notification_id", "missing-id")
            recipient_email = payload.get("recipient_email")
            template_id = payload.get("template_id")
            dynamic_data = payload.get("dynamic_data", {})

            logger.info(f"Processing notification [ID: {notification_id}] for {recipient_email} using template '{template_id}'")

            # Validate basic payload requirements
            if not recipient_email or not template_id:
                logger.error(f"[POISON MESSAGE] Missing recipient_email or template_id in payload: {payload}. Acking.")
                ch.basic_ack(delivery_tag=delivery_tag)
                return

            # 2. Check User Preferences (Opt-Out check)
            user_prefs = worker_cache_service.get_user_preferences(recipient_email)
            if user_prefs and user_prefs.get("email_opt_out", False):
                logger.info(
                    f"[OPT-OUT SUPPRESSED] Notification [ID: {notification_id}] skipped: "
                    f"Recipient {recipient_email} has opted out of notifications."
                )
                ch.basic_ack(delivery_tag=delivery_tag)
                return

            # 3. Retrieve Notification Template (Redis cache -> DB fallback)
            template = worker_cache_service.get_template(template_id)
            if not template:
                logger.error(
                    f"[POISON MESSAGE] Template '{template_id}' not found in cache or DB "
                    f"for notification [ID: {notification_id}]. Acking to prevent infinite loop."
                )
                ch.basic_ack(delivery_tag=delivery_tag)
                return

            # 4. Render Email Template using Jinja2
            try:
                rendered_subject, rendered_body = email_service.render_template(
                    subject_template_str=template["subject_template"],
                    body_template_str=template["body_template"],
                    dynamic_data=dynamic_data
                )
            except Exception as render_err:
                logger.error(
                    f"[POISON MESSAGE] Template rendering error for notification [ID: {notification_id}]: {render_err}. Acking."
                )
                ch.basic_ack(delivery_tag=delivery_tag)
                return

            # 5. Simulate Email Delivery (Structured Console Logging)
            email_service.send_simulated_email(
                recipient_email=recipient_email,
                rendered_subject=rendered_subject,
                rendered_body=rendered_body,
                notification_id=notification_id
            )

            # 6. Acknowledge successful processing to RabbitMQ
            ch.basic_ack(delivery_tag=delivery_tag)
            logger.info(f"Successfully processed and acknowledged notification [ID: {notification_id}]")

        except Exception as unhandled_err:
            logger.exception(
                f"[UNHANDLED EXCEPTION] Error processing message [ID: {notification_id}]: {unhandled_err}. "
                "Acknowledging to prevent poison loop."
            )
            try:
                ch.basic_ack(delivery_tag=delivery_tag)
            except Exception as ack_err:
                logger.error(f"Failed to ack message after error: {ack_err}")

    def start(self):
        self._is_running = True
        logger.info("Initializing Notification Worker Consumer Service...")
        self._touch_heartbeat()

        while self._is_running:
            try:
                self._connect()
                self._channel.basic_consume(
                    queue=worker_settings.RABBITMQ_QUEUE,
                    on_message_callback=self.process_message,
                    auto_ack=False  # Manual acknowledgment for zero message loss
                )
                logger.info(f"Worker listening for messages on queue: '{worker_settings.RABBITMQ_QUEUE}'...")
                
                # Start consuming messages
                self._channel.start_consuming()

            except pika.exceptions.AMQPConnectionError as conn_err:
                if self._is_running:
                    logger.warning(f"RabbitMQ connection lost: {conn_err}. Reconnecting in 5s...")
                    time.sleep(5)
            except Exception as e:
                if self._is_running:
                    logger.error(f"Unexpected worker loop exception: {e}. Reconnecting in 5s...")
                    time.sleep(5)

if __name__ == "__main__":
    worker = NotificationWorker()
    worker.start()
