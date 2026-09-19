import pytest

def test_api_validation_valid_request(client, mock_rabbitmq):
    """Ensure valid request returns HTTP 202 and notification_id."""
    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "order-confirmation",
        "dynamic_data": {
            "order_id": "1001",
            "customer_name": "Alice Smith",
            "product_name": "Mechanical Keyboard",
            "total_amount": "149.99"
        }
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert "notification_id" in data
    assert data["recipient_email"] == "alice@example.com"
    assert data["template_id"] == "order-confirmation"
    assert len(mock_rabbitmq.published_messages) == 1
    assert mock_rabbitmq.published_messages[0]["recipient_email"] == "alice@example.com"

def test_api_validation_invalid_email(client):
    """Ensure invalid email format triggers HTTP 400 Bad Request."""
    payload = {
        "recipient_email": "not-a-valid-email-address",
        "template_id": "order-confirmation",
        "dynamic_data": {"order_id": "1001"}
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data or "errors" in data

def test_api_validation_missing_recipient_email(client):
    """Ensure missing recipient_email triggers HTTP 400."""
    payload = {
        "template_id": "order-confirmation",
        "dynamic_data": {"order_id": "1001"}
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400

def test_api_validation_empty_template_id(client):
    """Ensure empty or whitespace template_id triggers HTTP 400."""
    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "   ",
        "dynamic_data": {"order_id": "1001"}
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400

def test_api_validation_missing_template_id(client):
    """Ensure missing template_id triggers HTTP 400."""
    payload = {
        "recipient_email": "alice@example.com",
        "dynamic_data": {"order_id": "1001"}
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400

def test_api_validation_invalid_dynamic_data_type(client):
    """Ensure non-object dynamic_data triggers HTTP 400."""
    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "order-confirmation",
        "dynamic_data": "not a dictionary object"
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400

def test_api_validation_nonexistent_template(client):
    """Ensure request with template not found in cache or DB returns HTTP 400."""
    payload = {
        "recipient_email": "alice@example.com",
        "template_id": "non-existent-promotional-template",
        "dynamic_data": {"key": "value"}
    }
    response = client.post("/api/notifications/email", json=payload)
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()
