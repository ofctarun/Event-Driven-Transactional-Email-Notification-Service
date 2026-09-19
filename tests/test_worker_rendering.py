import pytest
from worker.src.email_service import EmailService

def test_render_order_confirmation():
    svc = EmailService()
    subject_tmpl = "Order Confirmation - {{ order_id }}"
    body_tmpl = "Hello {{ customer_name }}, order #{{ order_id }} of {{ product_name }} is confirmed! Total: ${{ total_amount }}."
    data = {
        "order_id": "ORD-999",
        "customer_name": "Diana Prince",
        "product_name": "Lasso of Truth",
        "total_amount": "499.00"
    }

    subj, body = svc.render_template(subject_tmpl, body_tmpl, data)
    assert subj == "Order Confirmation - ORD-999"
    assert "Diana Prince" in body
    assert "ORD-999" in body
    assert "Lasso of Truth" in body
    assert "$499.00" in body

def test_render_password_reset():
    svc = EmailService()
    subject_tmpl = "Password Reset Request for {{ user_name }}"
    body_tmpl = "Hello {{ user_name }}, click {{ reset_link }} to reset password. Link expires in {{ expiry_minutes }} mins."
    data = {
        "user_name": "ClarkKent",
        "reset_link": "https://auth.example.com/reset?token=xyz",
        "expiry_minutes": 15
    }

    subj, body = svc.render_template(subject_tmpl, body_tmpl, data)
    assert subj == "Password Reset Request for ClarkKent"
    assert "https://auth.example.com/reset?token=xyz" in body
    assert "15 mins" in body

def test_render_account_alert():
    svc = EmailService()
    subject_tmpl = "Security Alert: New Sign-in from {{ device }}"
    body_tmpl = "Dear {{ user_name }}, sign-in from {{ device }} in {{ location }} on {{ login_time }}."
    data = {
        "user_name": "Bruce Wayne",
        "device": "Batcomputer Terminal 4",
        "location": "Gotham City",
        "login_time": "2026-09-19 20:30:00 UTC"
    }

    subj, body = svc.render_template(subject_tmpl, body_tmpl, data)
    assert subj == "Security Alert: New Sign-in from Batcomputer Terminal 4"
    assert "Bruce Wayne" in body
    assert "Gotham City" in body
