# API Reference Documentation

## Event-Driven Transactional Email Notification Service API

- **Base URL**: `http://localhost:8000`
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **OpenAPI JSON Spec**: `http://localhost:8000/openapi.json`

---

## 1. Endpoints Overview

| Method | Endpoint | Description | Expected Status Codes |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/notifications/email` | Enqueue a transactional email notification | `202 Accepted`, `400 Bad Request`, `429 Too Many Requests`, `500 Server Error` |
| `GET` | `/health` | System health check (API, Redis, RabbitMQ, DB) | `200 OK`, `503 Service Unavailable` |
| `GET` | `/api/health` | API alias health check | `200 OK`, `503 Service Unavailable` |
| `GET` | `/` | API Root service status | `200 OK` |

---

## 2. Endpoint Specifications

### 2.1 Enqueue Transactional Email

```http
POST /api/notifications/email HTTP/1.1
Host: localhost:8000
Content-Type: application/json
```

#### Request Headers
| Header | Type | Description |
| :--- | :--- | :--- |
| `Content-Type` | `string` | Must be `application/json` |
| `X-Forwarded-For` | `string` | (Optional) Client IP if behind a reverse proxy/load balancer |

#### Request Body Schema
| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `recipient_email` | `string (email)` | **Yes** | Valid recipient email address | `"alice@example.com"` |
| `template_id` | `string` | **Yes** | Identifier of a registered notification template | `"order-confirmation"` |
| `dynamic_data` | `object` | **Yes** | Key-value pairs matching variables in template | `{"order_id": "1001", "product_name": "Widget"}` |

#### Pre-Configured Templates Seeded in Database
1. **`order-confirmation`**
   - Variables: `order_id`, `customer_name`, `product_name`, `total_amount`
2. **`password-reset`**
   - Variables: `user_name`, `reset_link`, `expiry_minutes`
3. **`account-alert`**
   - Variables: `user_name`, `device`, `location`, `login_time`

#### Example Request Payload
```json
{
  "recipient_email": "alice@example.com",
  "template_id": "order-confirmation",
  "dynamic_data": {
    "order_id": "#98765",
    "customer_name": "Alice Smith",
    "product_name": "Ultra Keyboard Pro",
    "total_amount": "199.99"
  }
}
```

---

#### Success Response: `202 Accepted`
Returned immediately when the notification is validated and published to the message queue.

```json
{
  "status": "accepted",
  "notification_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "recipient_email": "alice@example.com",
  "template_id": "order-confirmation",
  "timestamp": "2026-09-19T15:30:00.000000Z",
  "message": "Notification request successfully accepted and queued for delivery"
}
```

---

#### Error Responses

##### `400 Bad Request` — Validation Error
Returned when the email is invalid, `template_id` is missing, or `dynamic_data` is not a JSON object.

```json
{
  "detail": "Input validation failed for email notification request.",
  "errors": [
    "body -> recipient_email: value is not a valid email address: The email address is not valid. It must have exactly one @-sign."
  ],
  "error_type": "ValidationError"
}
```

##### `400 Bad Request` — Non-Existent Template
Returned when the requested template does not exist in Redis cache or the database.

```json
{
  "detail": "Notification template 'unknown-promo-code' was not found."
}
```

##### `429 Too Many Requests` — Rate Limit Exceeded
Returned when the client IP exceeds the configured requests per minute (`RATE_LIMIT_PER_MINUTE`).

Response Headers:
```http
Retry-After: 42
```

Response Body:
```json
{
  "detail": "Rate limit exceeded. Maximum allowed requests reached. Try again in 42 seconds.",
  "error_type": "RateLimitExceeded",
  "retry_after_seconds": 42
}
```

---

### 2.2 Health Check

```http
GET /health HTTP/1.1
Host: localhost:8000
```

#### Success Response: `200 OK`
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

#### Degraded Response: `503 Service Unavailable`
```json
{
  "status": "degraded",
  "service": "email-notification-api",
  "components": {
    "database": "up",
    "redis": "up",
    "rabbitmq": "down"
  }
}
```

---

## 3. Quick cURL Commands for Testing

### Send Order Confirmation Email
```bash
curl -X POST http://localhost:8000/api/notifications/email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "alice@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-54321",
      "customer_name": "Alice Smith",
      "product_name": "Mechanical Keyboard",
      "total_amount": "129.99"
    }
  }'
```

### Send Password Reset Request
```bash
curl -X POST http://localhost:8000/api/notifications/email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "alice@example.com",
    "template_id": "password-reset",
    "dynamic_data": {
      "user_name": "AliceS",
      "reset_link": "https://example.com/auth/reset?token=xyz987",
      "expiry_minutes": "15"
    }
  }'
```

### Test User Opt-Out (Simulated Skip)
```bash
curl -X POST http://localhost:8000/api/notifications/email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "bob.optout@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-9999",
      "customer_name": "Bob",
      "product_name": "Widget",
      "total_amount": "10.00"
    }
  }'
```

### Health Check
```bash
curl -X GET http://localhost:8000/health
```
