"""`bulkhead` CLI: configure the tiered scorer, and install/pull what it needs.

  bulkhead setup --recommended     ONNX gate + Ollama judge (installs + pulls)
  bulkhead setup                   interactive wizard (asks before installing)
  bulkhead setup --reset           remove config (back to the regex default)
  bulkhead status                  show resolved config + backend reachability

Add --yes to auto-confirm installs (Ollama, pip extras) non-interactively.
Weights download on first use; nothing is bundled. Cloud judges send retrieved
content to the provider -- the wizard says so before you pick one.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from typing import Any

from .types import BulkheadConfig

EXTRA_DEPS = {
    "onnx": ["onnxruntime", "huggingface-hub", "tokenizers"],
    "transformers": ["transformers", "torch"],
    "llama_cpp": ["llama-cpp-python", "huggingface-hub"],
}
_IMPORT_PROBE = {"onnx": "onnxruntime", "transformers": "transformers", "llama_cpp": "llama_cpp"}
_EXTRA_NAME = {"onnx": "onnx", "transformers": "transformers", "llama_cpp": "llama"}


def _recommended_config() -> dict[str, Any]:
    return {
        "gate": {"runtime": "onnx", "model": "protectai/deberta-v3-base-prompt-injection-v2"},
        "judge": {"runtime": "ollama", "model": "llama3.2:3b"},
        "policy": {"policy": "warn", "judge_when": "suspicious_or_many"},
    }


# --- shell helpers -----------------------------------------------------------


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        print(f"{prompt} yes")
        return True
    try:
        return input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")
    except (EOFError, OSError):
        return False


def _run(cmd, shell: bool = False) -> int:
    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    try:
        return subprocess.call(cmd, shell=shell)
    except FileNotFoundError as exc:
        print(f"  [error] {exc}")
        return 1


def _pip_install(deps: list[str]) -> int:
    return _run([sys.executable, "-m", "pip", "install", *deps])


def _install_ollama() -> int:
    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            return _run([
                "winget", "install", "--id", "Ollama.Ollama", "-e", "--source", "winget",
                "--accept-source-agreements", "--accept-package-agreements",
            ])
        print("  winget not found. Download Ollama: https://ollama.com/download/windows")
        return 1
    if system == "Darwin":
        if shutil.which("brew"):
            return _run(["brew", "install", "ollama"])
        print("  Homebrew not found. Download Ollama: https://ollama.com/download")
        return 1
    if shutil.which("curl"):
        return _run("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
    print("  curl not found. See https://ollama.com/download/linux")
    return 1


def _ensure_extra(runtime: str, assume_yes: bool) -> bool:
    """Make sure a local runtime's deps are importable; offer to pip install."""
    probe = _IMPORT_PROBE.get(runtime)
    if not probe:
        return True
    try:
        __import__(probe)
        return True
    except ImportError:
        pass
    deps = EXTRA_DEPS.get(runtime, [])
    if _confirm(f"  {runtime} deps missing. pip install {' '.join(deps)}?", assume_yes):
        return _pip_install(deps) == 0
    print(f"  skipped. Install later: pip install 'bulkhead-ai[{_EXTRA_NAME.get(runtime, runtime)}]'")
    return False


# --- provisioning ------------------------------------------------------------


def _provision_gate(spec: dict, assume_yes: bool) -> None:
    rt = spec.get("runtime")
    if rt not in ("onnx", "transformers"):
        return
    model = spec.get("model", "")
    print(f"Gate: {rt} '{model}'.")
    if not _ensure_extra(rt, assume_yes):
        return
    try:
        if rt == "onnx":
            from .scorers import encoder_onnx

            print(f"  downloading model (~{encoder_onnx.DEFAULT_SIZE_MB}MB on first use)...")
            encoder_onnx.prepare(model)
        else:
            from .scorers import hf_transformers

            print("  downloading model...")
            hf_transformers.prepare(model)
        print("  smoke test passed.")
    except Exception as exc:  # noqa: BLE001
        print(f"  could not prepare gate ({type(exc).__name__}: {exc}).")


def _provision_ollama(model: str, assume_yes: bool) -> None:
    from .scorers import ollama as ol

    print(f"Judge: Ollama '{model}'.")
    if shutil.which("ollama") is None and not ol.is_available():
        if _confirm("  Ollama is not installed. Install it now?", assume_yes):
            _install_ollama()
        else:
            print("  install later: https://ollama.com/download")
            return
    if not ol.is_available():
        print("  Ollama isn't responding yet. Start it (`ollama serve` or launch the app), then re-run setup.")
        return
    print(f"  pulling {model} (large on first run; first inference also loads it into memory)...")
    try:
        seen = {"pct": -1}

        def on_progress(status: str, completed: int, total: int) -> None:
            if total:
                pct = int(completed * 100 / total)
                if pct != seen["pct"]:
                    seen["pct"] = pct
                    print(f"\r  {status}: {pct}%", end="", flush=True)

        ol.pull(model, progress=on_progress)
        print("\n  pulled. running smoke test...")
        ol.ollama_judge_factory({"model": model}, BulkheadConfig())(["smoke test"])
        print("  smoke test passed.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n  could not prepare judge ({type(exc).__name__}: {exc}).")


def _provision_judge(spec: dict, assume_yes: bool) -> None:
    rt = spec.get("runtime")
    if rt == "ollama":
        _provision_ollama(spec.get("model", ""), assume_yes)
    elif rt == "llama_cpp":
        print(f"Judge: llama_cpp '{spec.get('model', '')}' / '{spec.get('file', '')}'.")
        if _ensure_extra("llama_cpp", assume_yes):
            print("  (the GGUF downloads on first real use.)")
    elif rt == "cloud":
        key_env = spec.get("key_env", "")
        present = bool(os.environ.get(key_env))
        print(f"Judge: cloud '{spec.get('provider', '')}'. {key_env}: {'set' if present else 'NOT set'}")
        print("  PRIVACY: a cloud judge sends suspicious retrieved content to the provider.")
        if not present:
            print(f"  set it:  PowerShell: $env:{key_env}='...'   bash: export {key_env}=...")


def _provision(cfg: dict, assume_yes: bool) -> None:
    _provision_gate(cfg.get("gate") or {}, assume_yes)
    _provision_judge(cfg.get("judge") or {}, assume_yes)


# --- commands ----------------------------------------------------------------


def cmd_status() -> int:
    from . import config as cfgmod

    path = cfgmod.resolved_config_path()
    if path is None:
        print("No Bulkhead config. Using the regex default. Run `bulkhead setup`.")
        return 0
    raw = cfgmod.load_raw() or {}
    gate = raw.get("gate") or {"runtime": "regex"}
    judge = raw.get("judge") or {"runtime": "none"}
    policy = raw.get("policy") or {}
    print(f"Config: {path}")
    print(f"  gate : {gate.get('runtime', 'regex')} {gate.get('model', '')}".rstrip())
    print(f"  judge: {judge.get('runtime', 'none')} {judge.get('model', '')}".rstrip())
    print(f"  judge_when: {policy.get('judge_when', 'suspicious_or_many')}")
    print(f"  policy: {policy.get('policy', 'warn')}")
    if judge.get("runtime") == "ollama":
        from .scorers import ollama

        print(f"  ollama reachable: {ollama.is_available(judge.get('base_url') or ollama.DEFAULT_BASE_URL)}")
    if judge.get("runtime") == "cloud":
        key_env = judge.get("key_env", "")
        print(f"  cloud key {key_env}: {'set' if os.environ.get(key_env) else 'MISSING'}")
    return 0


def _parse_slot(value: str) -> dict[str, str]:
    runtime, _, model = value.partition(":")
    spec = {"runtime": runtime}
    if model:
        spec["model"] = model
    return spec


def cmd_setup(args: argparse.Namespace) -> int:
    from . import config as cfgmod

    if args.reset:
        removed = cfgmod.clear()
        print(f"Removed {removed}." if removed else "No config to remove.")
        return 0

    if args.recommended:
        cfg = _recommended_config()
        if args.judge_when:
            cfg["policy"]["judge_when"] = args.judge_when
    elif args.gate or args.judge:
        cfg = {
            "gate": _parse_slot(args.gate) if args.gate else {"runtime": "regex"},
            "judge": _parse_slot(args.judge) if args.judge else {"runtime": "none"},
            "policy": {"judge_when": args.judge_when or "suspicious_or_many"},
        }
        if args.gate and args.gate.startswith("cloud"):
            cfg["judge"].setdefault("key_env", args.key_env or "OPENAI_API_KEY")
        if args.judge and args.judge.startswith("cloud"):
            cfg["judge"] = {"runtime": "cloud", "provider": _parse_slot(args.judge).get("model", "openai"),
                            "key_env": args.key_env or "OPENAI_API_KEY"}
    else:
        return _interactive(cfgmod)

    path = cfgmod.save_raw(cfg)
    print(f"Wrote config to {path}")
    _provision(cfg, args.yes)
    print("Done. In Python: bh = Bulkhead.from_config()")
    return 0


def _interactive(cfgmod: Any) -> int:
    print("Bulkhead setup. Press enter to accept the [default].")
    gate_rt = input("  gate runtime [onnx/transformers/regex/none] (onnx): ").strip() or "onnx"
    gate: dict[str, str] = {"runtime": gate_rt}
    if gate_rt in ("onnx", "transformers"):
        gate["model"] = input(
            "  gate model (protectai/deberta-v3-base-prompt-injection-v2): "
        ).strip() or "protectai/deberta-v3-base-prompt-injection-v2"
    judge_rt = input("  judge runtime [ollama/cloud/llama_cpp/none] (ollama): ").strip() or "ollama"
    judge: dict[str, str] = {"runtime": judge_rt}
    if judge_rt in ("ollama", "llama_cpp"):
        judge["model"] = input("  judge model (llama3.2:3b): ").strip() or "llama3.2:3b"
        if judge_rt == "llama_cpp":
            judge["file"] = input("  gguf filename: ").strip()
    elif judge_rt == "cloud":
        judge["provider"] = input("  provider [openai/groq/anthropic] (openai): ").strip() or "openai"
        judge["model"] = input("  model (gpt-4o-mini): ").strip() or "gpt-4o-mini"
        judge["key_env"] = input("  env var holding the API key (OPENAI_API_KEY): ").strip() or "OPENAI_API_KEY"
    when = input("  judge_when [suspicious_or_many/gate_flagged/always/never] (suspicious_or_many): ").strip()
    cfg = {"gate": gate, "judge": judge, "policy": {"judge_when": when or "suspicious_or_many"}}
    path = cfgmod.save_raw(cfg)
    print(f"Wrote config to {path}")
    _provision(cfg, assume_yes=False)  # ask before installing anything
    print("Done. In Python: bh = Bulkhead.from_config()")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bulkhead", description="Configure Bulkhead scorers.")
    sub = parser.add_subparsers(dest="command")
    setup = sub.add_parser("setup", help="configure the gate/judge (and install/pull what they need)")
    setup.add_argument("--recommended", action="store_true", help="ONNX gate + Ollama judge")
    setup.add_argument("--reset", action="store_true", help="remove config (regex default)")
    setup.add_argument("--gate", help="runtime[:model], e.g. onnx:protectai/...")
    setup.add_argument("--judge", help="runtime[:model|provider], e.g. ollama:llama3.2:3b or cloud:groq")
    setup.add_argument("--key-env", dest="key_env", help="env var name holding a cloud key")
    setup.add_argument("--judge-when", dest="judge_when", help="never|gate_flagged|suspicious_or_many|always")
    setup.add_argument("--yes", action="store_true", help="auto-confirm installs (Ollama, pip extras)")
    sub.add_parser("status", help="show resolved config and backend reachability")

    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status()
    if args.command == "setup":
        return cmd_setup(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
