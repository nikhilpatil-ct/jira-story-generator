import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

# max_retries=0: we own retries in _with_retries below, so the SDK's built-in retry layer would only
# stack on top of ours and make backoff timing unpredictable.
_client = anthropic.AsyncAnthropic(max_retries=0)

ModelT = TypeVar("ModelT", bound=BaseModel)
R = TypeVar("R")


def _is_retryable(exc: Exception) -> bool:
    """Transient failures worth retrying: connection drops, timeouts, rate limits, and 5xx/overloaded."""
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)):
        return True  # APITimeoutError is a subclass of APIConnectionError; RateLimitError is 429
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500 or exc.status_code == 529  # 529 = overloaded
    return False


async def _with_retries(operation: Callable[[], Awaitable[R]], *, description: str) -> R:
    """Run an Anthropic API call, retrying transient failures with exponential backoff + jitter."""
    for attempt in range(1, settings.max_api_retries + 1):
        try:
            return await operation()
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            if attempt >= settings.max_api_retries:
                logger.error("%s failed after %d attempt(s): %s", description, attempt, exc)
                raise
            delay = settings.api_retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                description, attempt, settings.max_api_retries, exc, delay,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")  # loop either returns or raises


async def structured_call(
    *,
    system: str,
    messages: list[dict],
    output_format: type[ModelT],
    max_tokens: int = 4096,
    thinking: bool = True,
) -> ModelT:
    """Call Claude and parse the response directly into a Pydantic model."""
    kwargs: dict = {}
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    async def _call():
        return await _client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_format=output_format,
            **kwargs,
        )

    response = await _with_retries(_call, description=f"structured_call({output_format.__name__})")
    return response.parsed_output


async def text_call(*, system: str, messages: list[dict], model: str | None = None, max_tokens: int = 4096) -> str:
    """Call Claude and return plain text, no structured output. Lets callers pick a lighter/faster model."""

    async def _call():
        return await _client.messages.create(
            model=model or settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

    response = await _with_retries(_call, description="text_call")
    return "".join(block.text for block in response.content if block.type == "text")
