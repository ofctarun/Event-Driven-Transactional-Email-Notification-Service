from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

class EmailNotificationRequest(BaseModel):
    recipient_email: EmailStr = Field(
        ..., 
        description="Valid recipient email address",
        examples=["alice@example.com"]
    )
    template_id: str = Field(
        ..., 
        min_length=1,
        description="ID of the pre-configured notification template",
        examples=["order-confirmation"]
    )
    dynamic_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value dictionary containing dynamic template variables",
        examples=[{"order_id": "#12345", "product_name": "Widget Pro"}]
    )

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("template_id cannot be empty or whitespace")
        return v_stripped

    @field_validator("dynamic_data")
    @classmethod
    def validate_dynamic_data(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("dynamic_data must be a valid JSON object")
        return v

class NotificationQueuedResponse(BaseModel):
    status: str = Field(default="accepted", description="Status of the request")
    notification_id: str = Field(..., description="Unique UUID-v4 assigned to this notification")
    recipient_email: str = Field(..., description="Target recipient email")
    template_id: str = Field(..., description="Template ID queued")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of request ingestion")
    message: str = Field(
        default="Notification request successfully accepted and queued for delivery",
        description="Human readable confirmation"
    )

class HealthCheckResponse(BaseModel):
    status: str
    service: str = "email-notification-api"
    components: Dict[str, str]

class ErrorDetailResponse(BaseModel):
    detail: str
    error_type: Optional[str] = None
