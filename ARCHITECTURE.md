# System Architecture & Technical Design Document

## Event-Driven Transactional Email Notification Service API

---

### 1. Executive Summary & Design Goals

In high-scale modern applications (Fintech, E-commerce, SaaS), sending real-time transactional communications—such as order confirmations, password reset codes, and security alerts—synchronously within the primary web application request-response cycle causes severe performance degradation, tight coupling, and elevated risk of cascading failures.

This service implements a decoupled, event-driven architecture using:
- **FastAPI**: Lightweight, asynchronous REST API optimized for ultra-fast request ingestion and non-blocking I/O.
- **RabbitMQ**: AMQP message broker ensuring persistent, reliable message queuing with strict durability guarantees.
- **Redis**: High-speed, in-memory store powering atomic rate limiting and cache-aside read optimization for email templates and user preferences.
- **PostgreSQL**: ACID-compliant persistent database for template storage, versioning, and user preference management.
- **Worker Service**: Standalone background consumer executing user opt-out checks, dynamic Jinja2 template rendering, delivery simulation, and manual acknowledgment.

---

### 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Clients["Clients & Upstream Services"]
        ClientApp["E-commerce / SaaS / Auth Service"]
    end

    subgraph APILayer["API Ingestion Layer (FastAPI)"]
        API["API Service: POST /api/notifications/email"]
        Validator["Pydantic v2 Schema Validation"]
        RateLimiter["Redis IP Rate Limiter (INCR + TTL)"]
        APICache["Template & Prefs Cache Check"]
        Producer["RabbitMQ Producer (Persistent)"]
    end

    subgraph StorageLayer["Data & Caching Infrastructure"]
        RedisDB[("Redis 7 In-Memory Cache")]
        PostgresDB[("PostgreSQL 16 Database")]
        RabbitMQBroker[("RabbitMQ 3.13 Broker")]
    end

    subgraph WorkerLayer["Processing & Execution Layer"]
        WorkerConsumer["Worker Consumer Service"]
        OptOutFilter{"Opt-Out Check"}
        TemplateRenderer["Jinja2 Template Engine"]
        DeliverySimulator["Simulated Email Dispatch (Console Log)"]
        Acknowledge["RabbitMQ basic_ack"]
    end

    %% Client Interactions
    ClientApp -->|1. POST JSON Payload| API
    API --> Validator
    Validator --> RateLimiter
    RateLimiter <-->|Check / Increment IP| RedisDB
    RateLimiter -->|Pass| APICache
    APICache <-->|Cache-Aside (Hit/Miss)| RedisDB
    APICache -.->|DB Fallback on Miss| PostgresDB
    APICache --> Producer
    Producer -->|2. Publish Persistent Msg| RabbitMQBroker
    Producer -->|3. HTTP 202 Accepted| ClientApp

    %% Consumer Interactions
    RabbitMQBroker -->|4. Pull Event (Prefetch=10)| WorkerConsumer
    WorkerConsumer <-->|Lookup User Prefs| RedisDB
    WorkerConsumer --> OptOutFilter
    OptOutFilter -->|Opted-Out| Acknowledge
    OptOutFilter -->|Opt-In / Allowed| TemplateRenderer
    WorkerConsumer <-->|Lookup Template| RedisDB
    TemplateRenderer --> DeliverySimulator
    DeliverySimulator --> Acknowledge
    Acknowledge -->|5. basic_ack(delivery_tag)| RabbitMQBroker
```

---

### 3. Asynchronous Messaging & Queue Topologies (RabbitMQ)

#### 3.1 Durability & Zero Message Loss
- **Durable Queues & Exchanges**: The queue `email_notifications` and exchange `email_notifications_exchange` are declared with `durable=True`, ensuring all queues survive broker restarts.
- **Persistent Delivery Mode**: All published messages explicitly set `delivery_mode=2` (Persistent) and include unique UUID v4 message IDs and Unix timestamps.
- **Manual Acknowledgment (`auto_ack=False`)**: The worker consumer explicitly calls `channel.basic_ack(delivery_tag)` only after successfully processing the notification or classifying it as an unrecoverable poison message. If a worker container crashes during processing, unacknowledged messages are automatically requeued by RabbitMQ and delivered to a healthy replica.
- **Prefetch Control (`basic_qos(prefetch_count=10)`)**: Prevents a single worker node from monopolizing messages, guaranteeing fair load distribution across worker replicas.

#### 3.2 Poison Message & Dead-Letter Handling
A critical failure mode in distributed queues is the "poison message"—a malformed payload or template error that causes workers to crash and perpetually redeliver the bad message in an infinite loop.
- **Defensive Parsing & Validation**: Malformed JSON or unresolvable templates trigger immediate error logging and an explicit acknowledgment (`basic_ack`), removing the message from the hot queue.
- **Production Extension (DLX)**: For mission-critical production environments, poison messages can be routed to a Dead-Letter Exchange (`x-dead-letter-exchange: email_dlx`) after `N` retry attempts with exponential backoff.

---

### 4. Caching & Performance Optimization (Redis)

#### 4.1 Cache-Aside Pattern
Database reads for notification templates and user preferences can become severe bottlenecks under burst traffic.
- **Template Caching (`template:<template_id>`)**:
  1. API or Worker checks Redis for key `template:<template_id>`.
  2. Cache Hit: Parsed and utilized immediately (~1ms).
  3. Cache Miss: Queried from PostgreSQL, serialized to JSON, and cached in Redis with a 3600-second (1 hour) TTL.
- **User Notification Preferences (`user_prefs:email:<email>`)**:
  1. Checks Redis for `user_prefs:email:<email>`.
  2. Cache Hit: User opt-out status and language preference resolved instantly.
  3. Cache Miss: Queried from PostgreSQL and cached with a 3600-second TTL. If user does not exist, default preferences (opted-in, English) are cached to prevent repeated DB misses (Cache Penetration Defense).

#### 4.2 High-Throughput Rate Limiting
To prevent API abuse and DDoS attacks:
- **Key Pattern**: `rate_limit:ip:<client_ip>`.
- **Atomic Counter**: Uses Redis `pipeline()` with `INCR` and `TTL`.
- **Sliding Window Expiration**: On the first request from an IP within a 60-second window, an expiration of 60 seconds is set.
- **Threshold Breach**: If the count exceeds `RATE_LIMIT_PER_MINUTE`, the API immediately returns HTTP `429 Too Many Requests` along with a `Retry-After: <seconds>` response header.
- **High-Availability Fallback**: If Redis becomes temporarily unreachable, the rate limiter logs a warning and fails open to avoid blocking legitimate user transactions.

---

### 5. Data Models & Relational Schema (PostgreSQL)

#### 5.1 Tables
```sql
notification_templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

user_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_opt_out BOOLEAN DEFAULT FALSE NOT NULL,
    preferred_language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_user_preferences_email ON user_preferences(email);
```

---

### 6. Failure Modes & Resilience Strategies

| Failure Scenario | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **RabbitMQ Temporary Outage** | Ingestion blocked | API returns HTTP 500/503; worker automatically attempts reconnection with exponential backoff (up to 30 attempts). |
| **Redis Down** | Cache miss / rate limiting | Cache reads gracefully fall back to PostgreSQL database; rate limiter fails open with warning log. |
| **PostgreSQL Down** | Missed templates cannot be fetched | Active templates and user preferences continue serving directly from Redis cache without interruption. |
| **Malformed Dynamic Data** | Rendering error in worker | Worker catches Jinja2 syntax/undefined errors, logs structured poison event, and acks message without crashing or looping. |
| **Worker Node Crash** | In-flight message unacknowledged | RabbitMQ detects channel closure and redelivers the message to another active worker container. |

---

### 7. Horizontal Scalability & Production Roadmap

1. **Stateless API Replicas**: The FastAPI service holds no local state; scaling from 1 to 50 container instances behind an NGINX, ALB, or Kubernetes Ingress requires zero architectural changes.
2. **Dynamic Worker Scaling**: Worker consumers can be scaled dynamically (`docker compose up --scale worker=5`) based on RabbitMQ queue depth metrics (`rabbitmq_queue_messages_ready`).
3. **Queue Sharding & Partitioning**: For multi-million emails per hour, RabbitMQ Quorum Queues or RabbitMQ Stream plugins can be leveraged for high-throughput partitioned consumption.
4. **Email Delivery Provider Integration**: The modular `EmailService` can seamlessly swap the simulated logger for Amazon SES, SendGrid, Mailgun, or Postmark SMTP/API drivers via dependency injection.
