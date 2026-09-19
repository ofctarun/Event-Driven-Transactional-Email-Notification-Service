from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from ..database import check_db_connection
from ..services.cache_service import cache_service
from ..services.rabbitmq_producer import rabbitmq_producer

router = APIRouter(tags=["Health"])

@router.get("/health", summary="Service Health Check")
@router.get("/api/health", summary="API Health Check")
def health_check():
    db_ok = check_db_connection()
    redis_ok = cache_service.check_connection()
    rabbitmq_ok = rabbitmq_producer.check_connection()

    all_healthy = db_ok and redis_ok and rabbitmq_ok
    status_str = "healthy" if all_healthy else "degraded"
    http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    content = {
        "status": status_str,
        "service": "email-notification-api",
        "components": {
            "database": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
            "rabbitmq": "up" if rabbitmq_ok else "down",
        }
    }
    return JSONResponse(status_code=http_status, content=content)
