from __future__ import annotations

import pytest

from bulkhead import cli
from bulkhead import config as cfgmod


@pytest.fixture(autouse=True)
def _tmp_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BULKHEAD_CONFIG", str(tmp_path / "config.json"))
    # keep provisioning out of unit tests by default (no network/models/installs)
    monkeypatch.setattr(cli, "_provision", lambda *a, **k: None)


def test_setup_recommended_writes_config(capsys):
    rc = cli.main(["setup", "--recommended"])
    assert rc == 0
    raw = cfgmod.load_raw()
    assert raw["gate"]["runtime"] == "onnx"
    assert raw["judge"]["runtime"] == "ollama"
    assert raw["policy"]["judge_when"] == "suspicious_or_many"


def test_setup_flag_driven(capsys):
    rc = cli.main(["setup", "--gate", "onnx:my/model", "--judge", "none", "--judge-when", "always"])
    assert rc == 0
    raw = cfgmod.load_raw()
    assert raw["gate"] == {"runtime": "onnx", "model": "my/model"}
    assert raw["judge"] == {"runtime": "none"}
    assert raw["policy"]["judge_when"] == "always"


def test_setup_reset(capsys):
    cli.main(["setup", "--recommended"])
    assert cfgmod.load_raw() is not None
    rc = cli.main(["setup", "--reset"])
    assert rc == 0
    assert cfgmod.load_raw() is None


def test_status_no_config(capsys):
    rc = cli.main(["status"])
    assert rc == 0
    assert "No Bulkhead config" in capsys.readouterr().out


def test_status_with_config(capsys):
    cli.main(["setup", "--gate", "onnx:m", "--judge", "none"])
    rc = cli.main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "gate" in out and "onnx" in out


def test_provision_ollama_graceful_when_unreachable(capsys, monkeypatch):
    from bulkhead.scorers import ollama

    monkeypatch.setattr(ollama, "is_available", lambda *a, **k: False)
    monkeypatch.setattr(cli, "_confirm", lambda *a, **k: False)  # decline install prompt
    cli._provision_ollama("llama3.2:3b", assume_yes=False)  # must not raise
    out = capsys.readouterr().out.lower()
    assert "install later" in out or "responding" in out


def test_provision_gate_graceful_when_extra_declined(capsys, monkeypatch):
    monkeypatch.setattr(cli, "_ensure_extra", lambda *a, **k: False)
    cli._provision_gate({"runtime": "onnx", "model": "protectai/x"}, assume_yes=False)  # no raise
    assert "gate" in capsys.readouterr().out.lower()
