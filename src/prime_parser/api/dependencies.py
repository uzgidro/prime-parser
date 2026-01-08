"""API dependencies for authentication and configuration."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
import structlog

from prime_parser.configuration.settings import Settings, get_settings

logger = structlog.get_logger()

# API key header for incoming requests
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def validate_api_key(
    api_key: str = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate incoming API key.

    Args:
        api_key: API key from request header
        settings: Application settings

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid (401 Unauthorized)
    """
    if api_key != settings.api.incoming_api_key:
        logger.warning(
            "invalid_api_key_attempt",
            provided_key_prefix=api_key[:8] + "..." if len(api_key) > 8 else api_key,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    logger.debug("api_key_validated")
    return api_key


def get_settings_dependency() -> Settings:
    """Get settings dependency for FastAPI.

    Returns:
        Application settings
    """
    return get_settings()
