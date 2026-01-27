"""HTTP client for forwarding parsed data to external service."""

import httpx
import structlog
from typing import Any

from src.prime_parser.configuration.settings import ForwardingConfig
from src.prime_parser.models.domain_models import ParsedData
from src.prime_parser.utils.exceptions import ForwardingError
from src.prime_parser.utils.retry import retry_with_backoff

logger = structlog.get_logger()


class HTTPClient:
    """HTTP client for sending parsed data to external service."""

    def __init__(self, config: ForwardingConfig):
        """Initialize HTTP client.

        Args:
            config: Forwarding configuration
        """
        self.config = config
        logger.info(
            "http_client_initialized",
            endpoint=config.endpoint,
            timeout=config.timeout,
            max_attempts=config.retry.max_attempts,
        )

    async def send_data(self, data: ParsedData) -> dict[str, Any]:
        """Send parsed data to external service with retry logic.

        Args:
            data: Parsed data to send

        Returns:
            Response from external service

        Raises:
            ForwardingError: If data forwarding fails after all retries
        """
        logger.info(
            "sending_data_started",
            endpoint=self.config.endpoint,
            date=data.report_date.isoformat(),
            total_energy=str(data.total_energy_production),
        )

        try:
            result = await retry_with_backoff(
                func=lambda: self._send_request(data),
                max_attempts=self.config.retry.max_attempts,
                backoff_factor=self.config.retry.backoff_factor,
                max_delay=self.config.retry.max_delay,
                exceptions=(httpx.HTTPError, httpx.TimeoutException),
            )

            logger.info(
                "data_sent_successfully",
                endpoint=self.config.endpoint,
                response=result,
            )

            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                "data_forwarding_failed",
                endpoint=self.config.endpoint,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ForwardingError(
                f"Failed to forward data to {self.config.endpoint}: {e}"
            ) from e

    async def _send_request(self, data: ParsedData) -> dict[str, Any]:
        """Execute HTTP POST request to external service.

        Args:
            data: Parsed data to send

        Returns:
            Response JSON from external service

        Raises:
            httpx.HTTPError: If request fails
        """
        payload = {
            "date": data.report_date.isoformat(),
            "total_energy_production": float(data.total_energy_production),
        }

        headers = {
            "X-API-Key": self.config.api_key,
            "Content-Type": "application/json",
        }

        logger.debug(
            "http_request_sending",
            endpoint=self.config.endpoint,
            payload=payload,
            timeout=self.config.timeout,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.endpoint,
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )

            # Raise exception for HTTP error status codes
            response.raise_for_status()

            logger.debug(
                "http_response_received",
                status_code=response.status_code,
                response_text=response.text[:200],  # Log first 200 chars
            )

            # Try to parse JSON response
            try:
                return response.json()  # type: ignore[no-any-return]
            except Exception:
                # If response is not JSON, return status info
                return {
                    "status_code": response.status_code,
                    "text": response.text,
                }
