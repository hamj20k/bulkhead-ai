from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core import seal
from ..types import BulkheadConfig

if TYPE_CHECKING:
    from openai import OpenAI


def create_completion(
    client: "OpenAI",
    user: str,
    retrieved: str | list[str],
    model: str = "gpt-4o",
    config: BulkheadConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Seal ``retrieved`` and call OpenAI chat completions with the correct
    ``messages=[...]`` shape (system = guard, user = sealed JSON payload)."""
    sealed = seal(user, retrieved, config)
    return client.chat.completions.create(
        model=model,
        messages=sealed.to_messages(),
        **kwargs,
    )
