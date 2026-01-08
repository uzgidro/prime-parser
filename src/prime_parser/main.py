"""Main FastAPI application for PDF parser service."""

import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from prime_parser.api.routes import router
from prime_parser.configuration.settings import get_settings
from prime_parser.utils.exceptions import ConfigurationError


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


from typing import AsyncGenerator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    logger = structlog.get_logger()
    try:
        settings = get_settings()
        logger.info(
            "application_starting",
            environment=settings.environment,
            port=settings.api.port,
            log_level=settings.logging.level,
        )
    except ConfigurationError as e:
        logger.error("configuration_error", error=str(e))
        sys.exit(1)

    yield

    # Shutdown
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    # Load settings and configure logging
    try:
        settings = get_settings()
        configure_logging(settings.logging.level)
    except ConfigurationError as e:
        # If settings cannot be loaded, use default logging
        configure_logging("INFO")
        logger = structlog.get_logger()
        logger.error("failed_to_load_settings", error=str(e))
        raise

    # Create FastAPI app
    app = FastAPI(
        title="Prime Parser - PDF Hydropower Report Parser",
        description="Microservice for parsing PDF hydropower plant reports and forwarding data",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Include routes
    app.include_router(router, prefix="/api/v1", tags=["Parser"])

    # Add health check at root
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "prime-parser", "status": "running", "version": "1.0.0"}

    # Global exception handler
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: object, exc: ConfigurationError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Configuration error",
                "message": str(exc),
            },
        )

    logger = structlog.get_logger()
    logger.info(
        "fastapi_app_created",
        environment=settings.environment,
        docs_url="/docs",
        api_prefix="/api/v1",
    )

    return app


# Create app instance
app = create_app()
