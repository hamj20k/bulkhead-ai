from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core import seal
from ..types import BulkheadConfig

if TYPE_CHECKING:
    from anthropic import Anthropic


def create_message(
    client: "Anthropic",
    user: str,
    retrieved: str | list[str],
    model: str = "claude-haiku-4-5-20251001",
    config: BulkheadConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Seal ``retrieved`` and call the Anthropic Messages API. The guard goes in
    the dedicated top-level ``system`` parameter; the user turn is a sealed JSON
    payload with ``trusted_instruction`` and ``untrusted_inputs``."""
    sealed = seal(user, retrieved, config)
    return client.messages.create(
        model=model,
        **sealed.to_anthropic_params(),
        **kwargs,
    )
