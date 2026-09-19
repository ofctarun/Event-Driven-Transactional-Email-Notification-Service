import os
from dotenv import load_dotenv

load_dotenv()

class WorkerSettings:
    ENV: str = os.getenv("ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@database:5432/notification_db"
    )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    TEMPLATE_CACHE_TTL: int = int(os.getenv("TEMPLATE_CACHE_TTL", "3600"))
    USER_PREFS_CACHE_TTL: int = int(os.getenv("USER_PREFS_CACHE_TTL", "3600"))

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_QUEUE: str = os.getenv("RABBITMQ_QUEUE", "email_notifications")
    RABBITMQ_EXCHANGE: str = os.getenv("RABBITMQ_EXCHANGE", "email_notifications_exchange")
    RABBITMQ_ROUTING_KEY: str = os.getenv("RABBITMQ_ROUTING_KEY", "email.notification.send")
    RABBITMQ_PREFETCH_COUNT: int = int(os.getenv("RABBITMQ_PREFETCH_COUNT", "10"))

    # Heartbeat file for container healthcheck
    HEARTBEAT_FILE: str = os.getenv("HEARTBEAT_FILE", "/tmp/worker_heartbeat")

worker_settings = WorkerSettings()
