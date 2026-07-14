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


async def text_call(*, system: str, messages: list[dict], model: str | None = None, max_tokens: int = 4096) -> str:
    """Call Claude and return plain text, no structured output. Lets callers pick a lighter/faster model."""
    response = await _client.messages.create(
        model=model or settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")
