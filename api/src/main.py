import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import Base, engine
from .routes.health import router as health_router
from .routes.notifications import router as notifications_router
from .services.rabbitmq_producer import rabbitmq_producer

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("notification_api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting up Event-Driven Notification API Service...")
    # Attempt table creation if not already created (e.g., SQLite in tests or dev)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Database schema synchronization notice: {e}")

    yield

    # Shutdown actions
    logger.info("Shutting down Event-Driven Notification API Service...")
    rabbitmq_producer.close()

app = FastAPI(
    title="Event-Driven Transactional Email Notification Service API",
    description="High-performance asynchronous email dispatching API leveraging RabbitMQ and Redis caching.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Validation Error Handler to ensure HTTP 400 with helpful payload
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        errors.append(f"{field}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Input validation failed for email notification request.",
            "errors": errors,
            "error_type": "ValidationError"
        }
    )

# Register routers
app.include_router(health_router)
app.include_router(notifications_router)

@app.get("/", tags=["Root"])
def root():
    return {
        "service": "Event-Driven Transactional Email Notification Service API",
        "status": "online",
        "documentation": "/docs",
        "health": "/health"
    }
