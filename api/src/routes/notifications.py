import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.schemas import EmailNotificationRequest, NotificationQueuedResponse
from ..services.rate_limiter import rate_limiter
from ..services.cache_service import cache_service
from ..services.rabbitmq_producer import rabbitmq_producer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

def get_client_ip(request: Request) -> str:
    """Extract client IP, taking X-Forwarded-For into account for reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post(
    "/email",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=NotificationQueuedResponse,
    summary="Enqueue Transactional Email Notification",
    responses={
        202: {"description": "Notification successfully accepted and queued."},
        400: {"description": "Invalid input payload or non-existent template."},
        429: {"description": "Rate limit exceeded."},
        500: {"description": "Internal server error queuing event."},
    }
)
def send_email_notification(
    payload: EmailNotificationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    client_ip = get_client_ip(request)

    # 1. Rate Limiting Check via Redis
    allowed, count, retry_after = rate_limiter.is_rate_limited(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "detail": f"Rate limit exceeded. Maximum allowed requests reached. Try again in {retry_after} seconds.",
                "error_type": "RateLimitExceeded",
                "retry_after_seconds": retry_after,
            }
        )

    # 2. Caching Check: Template Retrieval (Redis -> DB fallback)
    template = cache_service.get_template(payload.template_id, db=db)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Notification template '{payload.template_id}' was not found."
        )

    # 3. Pre-fetch / Cache User Preferences (Redis -> DB fallback)
    cache_service.get_user_preferences(payload.recipient_email, db=db)

    # 4. Asynchronously Publish to RabbitMQ
    success, notification_id, error_msg = rabbitmq_producer.publish_notification(
        recipient_email=payload.recipient_email,
        template_id=payload.template_id,
        dynamic_data=payload.dynamic_data
    )

    if not success:
        logger.error(f"Failed to queue notification: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue notification message to message broker."
        )

    # 5. Return HTTP 202 Accepted immediately
    from datetime import datetime, timezone
    return NotificationQueuedResponse(
        status="accepted",
        notification_id=notification_id,
        recipient_email=payload.recipient_email,
        template_id=payload.template_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message="Notification request successfully accepted and queued for delivery"
    )
