"""Retry logic with exponential backoff."""

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    max_attempts: int,
    backoff_factor: float,
    max_delay: float,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Retry async function with exponential backoff.

    Args:
        func: Async function to retry
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor (delay = backoff_factor ** attempt)
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Result of the function

    Raises:
        Last exception if all retry attempts fail
    """
    for attempt in range(1, max_attempts + 1):
        try:
            result = await func()
            if attempt > 1:
                logger.info("retry_succeeded", attempt=attempt)
            return result

        except exceptions as e:
            if attempt == max_attempts:
                logger.error(
                    "max_retries_exceeded",
                    attempts=attempt,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            # Calculate delay with exponential backoff
            delay = min(backoff_factor**attempt, max_delay)

            logger.warning(
                "retry_attempt",
                attempt=attempt,
                max_attempts=max_attempts,
                delay_seconds=delay,
                error=str(e),
                error_type=type(e).__name__,
            )

            await asyncio.sleep(delay)

    # This should never be reached, but added for type safety
    raise RuntimeError("Retry logic error: exhausted all attempts without raising")
