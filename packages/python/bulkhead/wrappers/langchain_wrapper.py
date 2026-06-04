from __future__ import annotations

from typing import Any

from ..types import BulkheadConfig


def sealed_run(
    chain: Any,
    user: str,
    retrieved: str | list[str],
    config: BulkheadConfig | None = None,
    **kwargs: Any,
) -> Any:
    """Deprecated: legacy LangChain ``run`` flattens everything into one string.

    Bulkhead's security value comes from preserving a system/user message
    boundary. A single-string chain cannot preserve that boundary, so this
    wrapper is intentionally disabled instead of offering a misleading defense.
    Use a chat-model API that accepts separate system/user messages.
    """
    raise RuntimeError(
        "bulkhead.wrappers.langchain_wrapper.sealed_run is disabled because "
        "legacy LangChain chain.run() flattens system, instruction, and "
        "untrusted data into one string. Use a chat model/messages API instead."
    )
