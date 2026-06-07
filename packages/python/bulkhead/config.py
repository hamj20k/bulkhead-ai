"""Config file load/save + resolution into a (BulkheadConfig, gate, judge).

Stored as JSON (stdlib, read + write, works on Python 3.9+) to keep the core
dependency-free; TOML would require a third-party reader on <3.11 and a writer
everywhere. Same schema as the design, just JSON.

Lookup order for reading: ``$BULKHEAD_CONFIG`` -> project ``./.bulkhead.json``
-> ``$XDG_CONFIG_HOME/bulkhead/config.json`` (default ``~/.config/...``).

Resolution is OPT-IN via :func:`bulkhead.from_config`; a plain ``seal()`` never
reads the filesystem, so default behavior is unchanged.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Tuple

from .scorers import registry
from .types import AnyJudge, AnyScorer, BulkheadConfig, ScorerConfig

ENV_PATH = "BULKHEAD_CONFIG"

# runtime -> backend module (imported lazily so the dep is only loaded if used).
_BACKEND_MODULES = {
    "onnx": "bulkhead.scorers.encoder_onnx",
    "ollama": "bulkhead.scorers.ollama",
    "llama_cpp": "bulkhead.scorers.llamacpp",
    "transformers": "bulkhead.scorers.hf_transformers",
    "cloud": "bulkhead.scorers.cloud",
}


def default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "bulkhead" / "config.json"


def resolved_config_path() -> Path | None:
    """The config file that would be read, or None if none exists."""
    override = os.environ.get(ENV_PATH)
    if override:
        p = Path(override)
        return p if p.exists() else None
    local = Path.cwd() / ".bulkhead.json"
    if local.exists():
        return local
    default = default_config_path()
    return default if default.exists() else None


def writable_config_path() -> Path:
    """Where `bulkhead setup` writes (env override, else the default path)."""
    override = os.environ.get(ENV_PATH)
    return Path(override) if override else default_config_path()


def load_raw() -> dict[str, Any] | None:
    path = resolved_config_path()
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_raw(data: dict[str, Any]) -> Path:
    path = writable_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def clear() -> Path | None:
    """Remove the writable config file. Returns the removed path, or None."""
    path = writable_config_path()
    if path.exists():
        path.unlink()
        return path
    return None


def config_from_raw(raw: dict[str, Any]) -> BulkheadConfig:
    policy = raw.get("policy", {}) or {}
    return BulkheadConfig(
        policy=policy.get("policy", "warn"),
        scorer=ScorerConfig(
            threshold=policy.get("threshold", 0.7),
            check_unicode=policy.get("check_unicode", True),
        ),
        judge_when=policy.get("judge_when", "suspicious_or_many"),
        judge_min_chunks=policy.get("judge_min_chunks", 8),
        judge_on_error=policy.get("judge_on_error", "auto"),
        judge_timeout=policy.get("judge_timeout", 10.0),
    )


def _ensure_backend(runtime: str) -> None:
    """Import the backend module so it self-registers. Silent on ImportError --
    the registry then raises a helpful 'install the extra' error when building."""
    module = _BACKEND_MODULES.get(runtime)
    if module is None:
        return
    try:
        importlib.import_module(module)
    except ImportError:
        pass


def _needs_backend(spec: dict[str, Any] | None, builtins: tuple[str, ...]) -> str | None:
    if not spec:
        return None
    runtime = (spec.get("runtime") or "").lower()
    return None if runtime in builtins else runtime or None


def resolve_full() -> Tuple[
    BulkheadConfig | None, AnyScorer | None, AnyJudge | None, AnyJudge | None
]:
    """Load config and build (config, gate, sync judge, async judge). The async
    judge is used by aseal(); it is None when the runtime has no async path
    (aseal then falls back to the sync judge). Returns all-None with no config."""
    raw = load_raw()
    if raw is None:
        return None, None, None, None
    cfg = config_from_raw(raw)
    gate_spec = raw.get("gate")
    judge_spec = raw.get("judge")
    gate_rt = _needs_backend(gate_spec, ("", "regex", "none"))
    judge_rt = _needs_backend(judge_spec, ("", "none"))
    if gate_rt:
        _ensure_backend(gate_rt)
    if judge_rt:
        _ensure_backend(judge_rt)
    gate = registry.build_gate(gate_spec, cfg)
    judge = registry.build_judge(judge_spec, cfg)
    ajudge = registry.build_ajudge(judge_spec, cfg)
    return cfg, gate, judge, ajudge


def resolve() -> Tuple[BulkheadConfig | None, AnyScorer | None, AnyJudge | None]:
    """Load config and build (config, gate, judge). Returns (None, None, None)
    when no config file exists (caller falls back to defaults)."""
    cfg, gate, judge, _ = resolve_full()
    return cfg, gate, judge
