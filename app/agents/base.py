from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings

_client = anthropic.AsyncAnthropic()

ModelT = TypeVar("ModelT", bound=BaseModel)


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

    response = await _client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_format=output_format,
        **kwargs,
    )
    return response.parsed_output
