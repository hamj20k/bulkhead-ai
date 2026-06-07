"""
Bulkhead demo GUI — side-by-side "with vs without" + an interactive setup/test
terminal.

A tiny zero-framework local server (Python stdlib + optional model SDKs).

  /         the side-by-side soup-vs-sealed demo
  /setup    a guided "terminal" to configure the tiered scorer (gate/judge),
            install Ollama / pip extras, save API keys to .env, and test seal()

Everything runs server-side on 127.0.0.1; keys never touch the browser.

  python demo/gui/app.py          # then open http://127.0.0.1:8000
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "packages" / "python"))  # use the local package

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", "8000"))
MAX_TOKENS = 400

EXTRA_DEPS = {
    "onnx": ["onnxruntime", "huggingface-hub", "tokenizers"],
    "llama": ["llama-cpp-python", "huggingface-hub"],
    "transformers": ["transformers", "torch"],
    "openai": ["openai"],
    "anthropic": ["anthropic"],
    "groq": ["groq"],
}


def load_env() -> None:
    """Minimal .env loader. Reads .env from repo root or this dir; does not
    override variables already set in the environment."""
    for path in (ROOT / ".env", HERE / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env()


# --- the original soup-vs-sealed demo ---------------------------------------


def provider_for(model: str) -> str:
    return "anthropic" if model.lower().startswith("claude") else "groq"


def soup_call(user: str, retrieved: str):
    content = f"{user}\n\n{retrieved}" if retrieved.strip() else user
    msgs = [{"role": "user", "content": content}]
    return "", msgs, msgs


def _risk_payload(risk) -> dict:
    return {
        "score": risk.score,
        "flags": risk.flags,
        "confidence": risk.confidence,
        "matches": risk.raw_matches,
    }


def _config_summary(raw: dict | None) -> dict:
    gate = (raw or {}).get("gate") or {"runtime": "regex"}
    judge = (raw or {}).get("judge") or {"runtime": "none"}
    policy = (raw or {}).get("policy") or {}
    return {
        "gate": gate.get("runtime") or "regex",
        "gate_model": gate.get("model"),
        "judge": judge.get("runtime") or "none",
        "judge_model": judge.get("model") or judge.get("provider"),
        "judge_when": policy.get("judge_when", "suspicious_or_many"),
        "policy": policy.get("policy", "warn"),
        "threshold": policy.get("threshold", 0.7),
        "source": "saved setup config" if raw else "regex default",
    }


def sealed_call(provider: str, user: str, retrieved: str):
    """Bulkhead-sealed shape, built with the saved setup config."""
    if not retrieved.strip():
        msgs = [{"role": "user", "content": user}]
        return "", msgs, msgs, None

    from bulkhead import BulkheadConfig
    from bulkhead.config import resolve_full
    from bulkhead.core import _seal_with_risk

    cfg, gate, judge, _ = resolve_full()
    cfg = cfg or BulkheadConfig()
    sealed, risk = _seal_with_risk(user, retrieved, cfg, gate, judge)
    if provider == "anthropic":
        params = sealed.to_anthropic_params()  # {system, messages:[user]}
        display = [{"role": "system", "content": params["system"]}] + params["messages"]
        return params["system"], params["messages"], display, risk
    msgs = sealed.to_messages()  # [{system: guard}, {user: json payload}]
    return "", msgs, msgs, risk


def complete(provider: str, model: str, system: str, messages: list[dict]) -> str:
    if provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set — save it on the Setup page")
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("Anthropic SDK missing — pip install anthropic")
        kwargs = {"system": system} if system else {}
        resp = Anthropic().messages.create(
            model=model, max_tokens=MAX_TOKENS, messages=messages, **kwargs
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY not set — save it on the Setup page")
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("Groq SDK missing — pip install groq")
    resp = Groq().chat.completions.create(
        model=model, messages=messages, max_tokens=MAX_TOKENS, temperature=0
    )
    return resp.choices[0].message.content or ""


def run_pair(model: str, user: str, retrieved: str) -> dict:
    from bulkhead import config as cfgmod

    provider = provider_for(model)
    s0, m0, d0 = soup_call(user, retrieved)
    try:
        raw_config = cfgmod.load_raw()
    except Exception:
        raw_config = None
    try:
        s1, m1, d1, risk = sealed_call(provider, user, retrieved)
        protected = {"messages": d1, "risk": _risk_payload(risk) if risk else None}
        protected["response"] = complete(provider, model, s1, m1)
    except Exception as exc:
        from bulkhead.errors import BulkheadInjectionError

        if not isinstance(exc, BulkheadInjectionError):
            raise
        protected = {
            "messages": [],
            "response": "",
            "blocked": True,
            "error": str(exc),
            "risk": {
                "score": exc.score,
                "flags": exc.flags,
                "confidence": "high",
                "matches": [],
            },
        }
    return {
        "provider": provider,
        "config": _config_summary(raw_config),
        "without": {"messages": d0, "response": complete(provider, model, s0, m0)},
        "with": protected,
    }


# --- setup / test terminal backend ------------------------------------------


def _importable(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_has(model: str, models: list[str]) -> bool:
    if not model:
        return False
    if model in models:
        return True
    base = model.split(":")[0]
    return any(m.split(":")[0] == base for m in models)


def _hf_cached(repo_id: str) -> bool:
    if not repo_id:
        return False
    try:
        from huggingface_hub import scan_cache_dir

        return any(repo.repo_id == repo_id for repo in scan_cache_dir().repos)
    except Exception:
        return False


def _model_status(raw: dict | None, ollama_models: list[str]) -> list[dict]:
    """Is each locally-stored model the config points at actually downloaded?"""
    out: list[dict] = []
    if not raw:
        return out
    gate = raw.get("gate") or {}
    judge = raw.get("judge") or {}
    if gate.get("runtime") in ("onnx", "transformers") and gate.get("model"):
        out.append({"slot": "gate", "runtime": gate["runtime"], "model": gate["model"],
                    "ready": _hf_cached(gate["model"])})
    jr = judge.get("runtime")
    if jr == "ollama" and judge.get("model"):
        out.append({"slot": "judge", "runtime": "ollama", "model": judge["model"],
                    "ready": _ollama_has(judge["model"], ollama_models)})
    elif jr == "llama_cpp" and judge.get("model"):
        out.append({"slot": "judge", "runtime": "llama_cpp", "model": judge["model"],
                    "ready": _hf_cached(judge["model"])})
    elif jr == "cloud":
        out.append({"slot": "judge", "runtime": "cloud", "model": judge.get("provider") or "cloud",
                    "ready": bool(os.environ.get(judge.get("key_env", "")))})
    return out


def env_info() -> dict:
    from bulkhead import config as cfgmod
    from bulkhead.scorers import ollama as ol

    deps = {m: _importable(m) for m in (
        "onnxruntime", "tokenizers", "huggingface_hub", "llama_cpp",
        "transformers", "torch", "openai", "anthropic", "groq",
    )}
    keys = {k: bool(os.environ.get(k)) for k in
            ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    try:
        raw = cfgmod.load_raw()
    except Exception:
        raw = None
    # If the daemon answers on the port it is obviously installed, even when the
    # server process has a stale PATH that can't find the `ollama` executable.
    running = ol.is_available()
    ollama_models = _ollama_models() if running else []
    return {
        "os": platform.system(),
        "python": platform.python_version(),
        "deps": deps,
        "keys": keys,
        "ollama": {
            "installed": shutil.which("ollama") is not None or running,
            "running": running,
            "models": ollama_models,
        },
        "models": _model_status(raw, ollama_models),
        "config": raw,
        "config_path": str(cfgmod.writable_config_path()),
    }


def save_key_to_env(key_env: str, value: str) -> dict:
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    out, found = [], False
    for line in lines:
        if line.strip().startswith(f"{key_env}="):
            out.append(f"{key_env}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key_env}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key_env] = value
    return {"ok": True, "path": str(env_path), "key_env": key_env}


def apply_setup(body: dict) -> dict:
    from bulkhead import config as cfgmod

    cfg = {
        "gate": body.get("gate") or {"runtime": "regex"},
        "judge": body.get("judge") or {"runtime": "none"},
        "policy": {
            "judge_when": body.get("judge_when", "suspicious_or_many"),
            "policy": body.get("policy", "warn"),
        },
    }
    path = cfgmod.save_raw(cfg)
    return {"ok": True, "path": str(path), "config": cfg}


def reset_config() -> dict:
    from bulkhead import config as cfgmod

    removed = cfgmod.clear()
    return {"ok": True, "removed": str(removed) if removed else None}


def run_test(body: dict) -> dict:
    from bulkhead import BulkheadConfig
    from bulkhead.config import resolve_full
    from bulkhead.core import _seal_with_risk

    user = body.get("user", "")
    retrieved = body.get("retrieved") or []
    if isinstance(retrieved, str):
        retrieved = [retrieved]
    retrieved = [c for c in retrieved if str(c).strip()]
    test_policy = body.get("policy", "warn")

    cfg, gate, judge, _ = resolve_full()
    cfg = cfg or BulkheadConfig()
    config_policy = cfg.policy
    threshold = cfg.scorer.threshold
    # Evaluate WITHOUT raising (permissive) so we can always return full detail,
    # then decide the verdict against the requested test policy ourselves. Keep
    # the judge failure mode aligned to the test policy so judge_unavailable
    # still surfaces under strict.
    cfg.policy = "permissive"
    cfg.judge_on_error = "fail_closed" if test_policy == "strict" else "fail_open"
    sealed, risk = _seal_with_risk(user, retrieved, cfg, gate, judge)
    blocked = test_policy == "strict" and risk.score >= threshold
    return {
        "blocked": blocked,
        "score": risk.score,
        "flags": risk.flags,
        "confidence": risk.confidence,
        "matches": risk.raw_matches,  # regex hits + the judge's "reason"
        "threshold": threshold,
        "policy": test_policy,
        "config_policy": config_policy,
        "guard": sealed.guard,
        "data": sealed.data,
    }


# --- streaming command runners (yield text lines) ---------------------------


def stream_subprocess(cmd, shell: bool = False):
    printed = cmd if isinstance(cmd, str) else " ".join(cmd)
    yield f"$ {printed}\n"
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, shell=shell,
        )
    except FileNotFoundError as exc:
        yield f"[error] {exc}\n"
        return
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line
    proc.wait()
    yield f"\n[exit {proc.returncode}]\n"


def ollama_install_stream():
    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            yield from stream_subprocess([
                "winget", "install", "--id", "Ollama.Ollama", "-e", "--source", "winget",
                "--accept-source-agreements", "--accept-package-agreements",
            ])
        else:
            yield "winget not found. Download Ollama: https://ollama.com/download/windows\n"
    elif system == "Darwin":
        if shutil.which("brew"):
            yield from stream_subprocess(["brew", "install", "ollama"])
        else:
            yield "Homebrew not found. Download Ollama: https://ollama.com/download\n"
    else:
        if shutil.which("curl"):
            yield from stream_subprocess("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
        else:
            yield "curl not found. See https://ollama.com/download/linux\n"


def ollama_pull_stream(model: str):
    from bulkhead.scorers import ollama as ol

    if not model:
        yield "[error] no model specified\n"
        return
    if not ol.is_available():
        yield "Ollama is not running at localhost:11434. Install/start it first.\n"
        return
    yield f"Pulling {model} (first run can be large)...\n"
    body = json.dumps({"name": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{ol.DEFAULT_BASE_URL}/api/pull", data=body,
        headers={"Content-Type": "application/json"},
    )
    last = -1
    try:
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line.decode("utf-8"))
                status = ev.get("status", "")
                total = int(ev.get("total", 0) or 0)
                completed = int(ev.get("completed", 0) or 0)
                if total:
                    pct = int(completed * 100 / total)
                    if pct != last:
                        last = pct
                        yield f"{status}: {pct}%\n"
                else:
                    yield f"{status}\n"
    except Exception as exc:  # noqa: BLE001
        yield f"[error] {exc}\n"
        return
    yield "[done] pulled. First inference may pause while the model loads into memory.\n"


def pip_install_stream(extra: str):
    deps = EXTRA_DEPS.get(extra)
    if not deps:
        yield f"[error] unknown extra {extra!r}\n"
        return
    yield f"Installing {extra} deps: {', '.join(deps)}\n"
    yield from stream_subprocess([sys.executable, "-m", "pip", "install", *deps])


# --- HTTP --------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def _stream(self, generator):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for chunk in generator:
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path in ("/setup", "/setup.html"):
            self._send(200, (HERE / "setup.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/env":
            self._json(env_info())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        try:
            if self.path == "/run":
                req = self._body()
                self._json(run_pair(
                    req.get("model", "llama-3.1-8b-instant"),
                    req.get("user", ""),
                    req.get("retrieved", ""),
                ))
            elif self.path == "/api/setup":
                self._json(apply_setup(self._body()))
            elif self.path == "/api/reset":
                self._json(reset_config())
            elif self.path == "/api/test":
                self._json(run_test(self._body()))
            elif self.path == "/api/save-key":
                b = self._body()
                self._json(save_key_to_env(b.get("key_env", ""), b.get("value", "")))
            elif self.path == "/api/ollama/install":
                self._stream(ollama_install_stream())
            elif self.path == "/api/ollama/pull":
                self._stream(ollama_pull_stream(self._body().get("model", "")))
            elif self.path == "/api/pip-install":
                self._stream(pip_install_stream(self._body().get("extra", "")))
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as exc:  # surface errors to the UI
            self._json({"error": str(exc)}, code=200)


def main() -> int:
    print(f"Bulkhead demo GUI -> http://{HOST}:{PORT}")
    print(f"  side-by-side demo : http://{HOST}:{PORT}/")
    print(f"  setup & test term : http://{HOST}:{PORT}/setup")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
