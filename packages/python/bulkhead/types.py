from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

PolicyMode = Literal["strict", "warn", "permissive"]
Confidence = Literal["low", "medium", "high"]


@dataclass
class ScorerConfig:
    threshold: float = 0.7
    check_unicode: bool = True


@dataclass
class BulkheadConfig:
    policy: PolicyMode = "warn"
    scorer: ScorerConfig = field(default_factory=ScorerConfig)


@dataclass
class RiskResult:
    score: float
    flags: list[str]
    confidence: Confidence
    raw_matches: list[str]


# A scorer is any callable that maps content to a RiskResult. Swap the built-in
# regex scorer for your own (e.g. an LLM judge or hosted detector).
Scorer = Callable[[str], RiskResult]


@dataclass
class SealOutput:
    """The result of seal().

    Holds the three pieces of a sealed request and renders them into the right
    shape per SDK. The key invariant: the untrusted retrieved content is placed
    in the ``untrusted_inputs`` field of a JSON **user** message, never in
    ``system``. The trusted ``instruction`` stays authoritative as the
    ``trusted_instruction`` field; ``guard`` is a system preamble explaining the
    JSON boundary.

    ``**`` unpacking yields ``{"messages": [...]}`` (OpenAI shape), so
    ``client.chat.completions.create(model=..., **sealed)`` works directly. For
    Anthropic use :meth:`to_anthropic_params`.
    """

    instruction: str
    data: str  # JSON payload; "" when nothing was retrieved
    guard: str  # system preamble; "" when nothing was retrieved

    @property
    def prompt(self) -> str:
        """Back-compat alias for the (untouched) user instruction."""
        return self.instruction

    def to_messages(self, data_role: str = "user") -> list[dict[str, str]]:
        """OpenAI-compatible messages array.

        ``[{system: guard}, {<data_role>: json_payload}]`` when retrieved data
        exists. If there is no retrieved data, this returns only the instruction
        message. Retrieved content sits in a data-position message (``user`` by
        default), never ``system``.
        """
        messages: list[dict[str, str]] = []
        if self.guard:
            messages.append({"role": "system", "content": self.guard})
        if self.data:
            messages.append({"role": data_role, "content": self.data})
        else:
            messages.append({"role": "user", "content": self.instruction})
        return messages

    def to_anthropic_params(self) -> dict[str, Any]:
        """Anthropic SDK params. The Anthropic API rejects consecutive user
        messages, so the JSON payload is sent as a single user turn. The
        ``guard`` goes in the top-level ``system`` -- never the untrusted data.

        Use as ``client.messages.create(model=..., **sealed.to_anthropic_params())``.
        """
        content = self.data if self.data else self.instruction
        return {
            "system": self.guard,
            "messages": [{"role": "user", "content": content}],
        }

    def to_dict(self) -> dict[str, Any]:
        return {"messages": self.to_messages()}

    # --- mapping protocol so ``**seal(...)`` works (OpenAI messages shape) ---
    def keys(self) -> Any:
        return self.to_dict().keys()

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]
