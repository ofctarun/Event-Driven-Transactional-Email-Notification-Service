# Event-Driven Transactional Email Notification Service API

[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-Ready-blue.svg)](docker-compose.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600.svg)](https://www.rabbitmq.com)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB.svg)](https://www.python.org)

An enterprise-grade, event-driven transactional email notification service designed to handle asynchronous email delivery at scale. Decouples client requests from email rendering and sending using **RabbitMQ**, while maximizing read throughput and protecting endpoints with a **Redis** caching and rate-limiting layer.

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start with Docker Compose](#quick-start-with-docker-compose)
- [Running Locally (Without Docker)](#running-locally-without-docker)
- [Database Schema & Seed Data](#database-schema--seed-data)
- [API Reference & Usage](#api-reference--usage)
- [Automated Testing](#automated-testing)
- [Caching Strategy & Rate Limiting](#caching-strategy--rate-limiting)
- [Reliability & Poison Message Protection](#reliability--poison-message-protection)
- [Environment Variables](#environment-variables)
- [License](#license)

---

## Architecture Overview

```
                      +-----------------------------+
                      | Client / Upstream Service   |
                      +-----------------------------+
                                     |
                       POST /api/notifications/email
                                     v
                      +-----------------------------+
                      |     FastAPI API Service     |
                      | - Pydantic Input Validation |
                      | - Redis IP Rate Limiting    |
                      | - Cache-Aside Template Read |
                      +-----------------------------+
                                /            \
                Check & Cache  /              \ Publish Persistent Event
                              v                v
                 +-------------------+    +----------------------+
                 |    Redis Cache    |    | RabbitMQ Message Bus |
                 | - rate_limit:ip:* |    | - Durable Exchange   |
                 | - template:*      |    | - Durable Queue      |
                 | - user_prefs:*    |    +----------------------+
                 +-------------------+               |
                           ^                         | Pull Event (Prefetch=10)
                 Fallback  |                         v
                 On Miss   |              +----------------------+
                 +-------------------+    |    Worker Service    |
                 | PostgreSQL 16 DB  |    | - User Opt-Out Check |
                 | - Templates       |    | - Jinja2 Rendering   |
                 | - User Prefs      |    | - Simulated Dispatch |
                 +-------------------+    | - Manual Ack / DLQ   |
                                          +----------------------+
```

### Flow Breakdown
1. **Request Ingestion**: Upstream client dispatches a transactional email request (`POST /api/notifications/email`).
2. **Rate Limiting**: Redis validates that the client IP has not exceeded the configured rate limit (`RATE_LIMIT_PER_MINUTE`). If exceeded, HTTP `429 Too Many Requests` is returned with a `Retry-After` header.
3. **Template Resolution**: The API queries Redis for the requested template. On cache miss, it reads from PostgreSQL and caches the template with a configurable TTL. If non-existent, HTTP `400 Bad Request` is returned.
4. **Asynchronous Queuing**: The event is published to RabbitMQ with `delivery_mode=2` (persistent message) on a durable queue.
5. **Immediate Acknowledgment**: The API returns HTTP `202 Accepted` immediately with a unique `notification_id` (UUID v4).
6. **Worker Processing**: The background Worker pulls the event, resolves recipient preferences from Redis/PostgreSQL, evaluates opt-out status, dynamically renders the email using **Jinja2**, logs the simulated dispatch, and explicitly acknowledges the message (`basic_ack`).

---

## Key Features

- **Non-Blocking REST API**: Built on FastAPI and ASGI for lightning-fast sub-millisecond request ingestion.
- **Durable RabbitMQ Integration**: Guaranteed message durability (`delivery_mode=2`), manual message acknowledgments (`basic_ack`), and prefetch QoS (`prefetch_count=10`).
- **Strategic Redis Caching**: Cache-aside pattern for both notification templates and user preferences to eliminate repetitive database roundtrips.
- **Sliding Window Rate Limiter**: IP-based atomic rate limiting protecting against abuse and traffic spikes.
- **Dynamic Jinja2 Templating**: High-flexibility email templating supporting variables, loops, and conditions.
- **User Notification Opt-Out**: Automatic preference enforcement skipping dispatch for opted-out users without losing message acknowledgment.
- **Poison Message Defense**: Malformed or unprocessable messages are safely caught, logged, and acknowledged to prevent infinite requeue loops.
- **Container Health Checks**: Native health checks on all containers (API, Worker, RabbitMQ, Redis, PostgreSQL) orchestrating safe startup ordering.

---

## Project Structure

```
.
├── .env.example                     # Environment variables configuration template
├── .gitignore                       # Git ignore rules
├── docker-compose.yml               # Multi-container orchestration with health checks
├── README.md                        # Project documentation
├── ARCHITECTURE.md                  # Detailed architectural design and trade-offs
├── API_DOCS.md                      # Complete API endpoint specifications
├── requirements-test.txt            # Test dependencies
├── database/
│   └── init-db.sql                  # Database schema & automated sample seeding
├── api/
│   ├── Dockerfile                   # Multi-stage slim container image for API
│   ├── requirements.txt             # API dependencies
│   └── src/
│       ├── main.py                  # FastAPI application entrypoint & exception handlers
│       ├── config.py                # Environment configuration
│       ├── database.py              # SQLAlchemy database engine and session
│       ├── models/
│       │   ├── db_models.py         # SQLAlchemy models (Templates, Preferences)
│       │   └── schemas.py           # Pydantic v2 schemas and validation
│       ├── routes/
│       │   ├── health.py            # Health check endpoint
│       │   └── notifications.py     # POST /api/notifications/email controller
│       └── services/
│           ├── cache_service.py     # Redis cache-aside logic
│           ├── rate_limiter.py      # Redis sliding-window rate limiter
│           └── rabbitmq_producer.py # Persistent RabbitMQ publisher
├── worker/
│   ├── Dockerfile                   # Worker container image with heartbeat healthcheck
│   ├── requirements.txt             # Worker dependencies
│   └── src/
│       ├── consumer.py              # RabbitMQ consumer loop with poison defense
│       ├── config.py                # Worker configuration
│       ├── database.py              # Worker database access
│       ├── cache_service.py         # Worker cache lookup (Redis -> DB)
│       └── email_service.py         # Jinja2 template rendering and simulated logger
└── tests/
    ├── conftest.py                  # In-memory SQLite, mock Redis, and mock RabbitMQ
    ├── test_api_validation.py       # Pydantic validation tests
    ├── test_rate_limiter.py         # Redis rate limiter tests
    ├── test_cache_service.py        # Cache hit/miss/invalidation tests
    ├── test_worker_rendering.py     # Jinja2 rendering tests
    ├── test_worker_opt_out.py       # Opt-out suppression tests
    ├── test_poison_message.py       # Poison message safety tests
    └── test_integration_flow.py     # End-to-end integration flow tests
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v24.0+) & [Docker Compose](https://docs.docker.com/compose/) (v2.20+)
- Python 3.12 or 3.13 (if running or testing locally)

---

## Quick Start with Docker Compose

To launch the entire distributed architecture with a single command:

```bash
# 1. Clone the repository and navigate into it
git clone <repo-url>
cd Event-Driven-Transactional-Email-Notification-Service

# 2. Copy environment variables
cp .env.example .env

# 3. Build and launch all services
docker-compose up --build
```

Docker Compose will start all 5 services in order:
1. `database` (PostgreSQL 16) — Initializes schema and seeds data via `database/init-db.sql`.
2. `redis` (Redis 7) — Ready for caching and rate limiting.
3. `rabbitmq` (RabbitMQ 3.13 Management) — Sets up message broker.
4. `api` — Starts after database, redis, and rabbitmq report healthy. Exposed at port `8000`.
5. `worker` — Starts after dependencies report healthy and begins consuming queue messages.

### Management Interfaces
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Documentation (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **RabbitMQ Management UI**: [http://localhost:15672](http://localhost:15672) (User: `guest`, Password: `guest`)

---

## Running Locally (Without Docker)

If you have local instances of PostgreSQL, Redis, and RabbitMQ running:

```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r api/requirements.txt
pip install -r worker/requirements.txt
pip install -r requirements-test.txt

# 3. Configure environment
cp .env.example .env
# Edit .env to point to your localhost services

# 4. Start the API Service
uvicorn api.src.main:app --host 0.0.0.0 --port 8000 --reload

# 5. In a separate terminal, start the Worker Service
python worker/src/consumer.py
```

---

## Database Schema & Seed Data

The database initializes automatically on first startup with tables `notification_templates` and `user_preferences`.

### Seeded Notification Templates
| Template ID | Name | Variables |
| :--- | :--- | :--- |
| `order-confirmation` | Order Confirmation | `order_id`, `customer_name`, `product_name`, `total_amount` |
| `password-reset` | Password Reset Request | `user_name`, `reset_link`, `expiry_minutes` |
| `account-alert` | Security Account Alert | `user_name`, `device`, `location`, `login_time` |

### Seeded User Preferences
| User ID | Email | Email Opt-Out | Preferred Language |
| :--- | :--- | :--- | :--- |
| `usr-001` | `alice@example.com` | `False` | `en` |
| `usr-002` | `bob.optout@example.com` | `True` *(Will be skipped)* | `en` |
| `usr-003` | `carlos@example.es` | `False` | `es` |
| `usr-004` | `diana@example.fr` | `False` | `fr` |
| `usr-005` | `evan@example.com` | `False` | `en` |

---

## API Reference & Usage

### 1. Enqueue Transactional Email
`POST /api/notifications/email`

#### Request Payload:
```json
{
  "recipient_email": "alice@example.com",
  "template_id": "order-confirmation",
  "dynamic_data": {
    "order_id": "ORD-12345",
    "customer_name": "Alice Smith",
    "product_name": "Ultra Noise-Cancelling Headphones",
    "total_amount": "299.99"
  }
}
```

#### Response (`202 Accepted`):
```json
{
  "status": "accepted",
  "notification_id": "8c6b7e61-897d-4113-94c0-26477e684074",
  "recipient_email": "alice@example.com",
  "template_id": "order-confirmation",
  "timestamp": "2026-09-19T15:10:00.000000Z",
  "message": "Notification request successfully accepted and queued for delivery"
}
```

#### cURL Example:
```bash
curl -X POST http://localhost:8000/api/notifications/email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "alice@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-12345",
      "customer_name": "Alice Smith",
      "product_name": "Ultra Noise-Cancelling Headphones",
      "total_amount": "299.99"
    }
  }'
```

---

### 2. User Opt-Out Demonstration
When sending to an opted-out user (e.g. `bob.optout@example.com`):

```bash
curl -X POST http://localhost:8000/api/notifications/email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "bob.optout@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-5555",
      "customer_name": "Bob",
      "product_name": "Widget",
      "total_amount": "19.99"
    }
  }'
```

**Worker Output:**
```
[INFO] [Worker] [OPT-OUT SUPPRESSED] Notification [ID: ...] skipped: Recipient bob.optout@example.com has opted out of notifications.
```

---

### 3. Rate Limiting Demonstration
If a client sends more than `RATE_LIMIT_PER_MINUTE` (default: 60) requests within 60 seconds:

#### Response (`429 Too Many Requests`):
```json
{
  "detail": "Rate limit exceeded. Maximum allowed requests reached. Try again in 45 seconds.",
  "error_type": "RateLimitExceeded",
  "retry_after_seconds": 45
}
```

---

### 4. Health Check
`GET /health`

#### Response (`200 OK`):
```json
{
  "status": "healthy",
  "service": "email-notification-api",
  "components": {
    "database": "up",
    "redis": "up",
    "rabbitmq": "up"
  }
}
```

---

## Automated Testing

The project includes unit and integration tests covering API input validation, rate limiting, caching, template rendering, opt-out suppression, and poison message handling.

### Run Tests Locally:
```bash
python -m pytest tests/ -v
```

### Run Tests Inside Docker:
```bash
docker-compose exec api pytest tests/ -v
```

### Test Coverage Highlights:
- **`test_api_validation.py`**: Validates proper email formatting, template ID requirement, dynamic data type assertions, and missing template rejection.
- **`test_rate_limiter.py`**: Validates request count increments, limit breaching, and HTTP 429 response structure.
- **`test_cache_service.py`**: Validates cache miss -> DB fallback -> Redis write -> cache hit cycles and cache invalidation.
- **`test_worker_rendering.py`**: Validates dynamic Jinja2 subject and body interpolation.
- **`test_worker_opt_out.py`**: Validates that opted-out recipients are safely skipped and acknowledged.
- **`test_poison_message.py`**: Validates corrupted payloads or missing templates are acknowledged and do not freeze the worker queue.
- **`test_integration_flow.py`**: Simulates the complete API -> RabbitMQ -> Worker -> Simulated Send pipeline.

---

## Caching Strategy & Rate Limiting

- **Cache Keys**:
  - Templates: `template:<template_id>` (TTL: 3600 seconds)
  - Preferences: `user_prefs:email:<email>` (TTL: 3600 seconds)
  - Rate Limits: `rate_limit:ip:<client_ip>` (TTL: 60 seconds sliding window)
- **Cache-Aside Pattern**: Requests check Redis first. If missing, data is queried from PostgreSQL and populated in Redis with expiration to guarantee fresh reads after schema changes.

---

## Reliability & Poison Message Protection

1. **Persistent Messages**: Messages in RabbitMQ use `delivery_mode=2` and survive broker restarts.
2. **Explicit Acknowledgment**: Messages are acknowledged (`channel.basic_ack`) only after successful rendering and logging.
3. **Poison Message Defense**: Malformed JSON, undefined variables, or invalid templates are trapped inside `try/except` blocks, logged with full error context, and acknowledged to RabbitMQ to prevent the queue from stalling.

---

## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `API_PORT` | `8000` | Port for FastAPI HTTP server |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per minute per IP address |
| `DATABASE_URL` | `postgresql://postgres:postgres@database:5432/notification_db` | PostgreSQL connection string |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `TEMPLATE_CACHE_TTL` | `3600` | Template cache TTL in seconds |
| `USER_PREFS_CACHE_TTL` | `3600` | User preference cache TTL in seconds |
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ broker hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `RABBITMQ_QUEUE` | `email_notifications` | Destination queue name |
| `RABBITMQ_PREFETCH_COUNT`| `10` | Consumer prefetch QoS setting |

---

## License
MIT License. Created for the Transactional Email Notification Service API project.
