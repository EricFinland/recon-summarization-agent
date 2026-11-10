"""CLI tests: exit codes, output file, and --stdout. No network (LLM provider "none")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from recon_agent import __main__ as cli
from recon_agent.loader import ScanLoadError

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def env(tmp_path, monkeypatch) -> Path:
    """Point every setting at tmp_path so a developer's .env cannot leak into the test."""
    out = tmp_path / "out"
    for key, value in {
        "LLM_PROVIDER": "none",
        "LLM_MODEL": "",
        "LLM_API_KEY": "",
        "SCAN_INPUT_DIR": str(ROOT / "data" / "scans"),
        "OUTPUT_DIR": str(out),
        "AUDIT_LOG_PATH": str(tmp_path / "audit.log.jsonl"),
    }.items():
        monkeypatch.setenv(key, value)
    return out


def test_default_run_writes_valid_summary(env, schema, capsys):
    assert cli.main([]) == cli.EXIT_OK

    written = env / "sample_scan_01.summary.json"
    assert f"Summary written to {written}" in capsys.readouterr().out
    errors = list(Draft202012Validator(schema).iter_errors(json.loads(written.read_text())))
    assert errors == []
    assert (env.parent / "audit.log.jsonl").stat().st_size > 0


def test_stdout_flag_prints_only_json(env, sample_scan_path, tmp_path, capsys):
    other = tmp_path / "elsewhere"
    code = cli.main(["--input", str(sample_scan_path), "--output-dir", str(other), "--stdout"])

    assert code == cli.EXIT_OK
    printed = json.loads(capsys.readouterr().out)
    assert printed["source"]["scan_file"] == "sample_scan_01.json"
    assert (other / "sample_scan_01.summary.json").exists()


def test_missing_input_exits_2(env, tmp_path, capsys):
    assert cli.main(["--input", str(tmp_path / "nope.json")]) == cli.EXIT_LOAD_ERROR
    assert "could not load" in capsys.readouterr().err


def test_load_error_from_pipeline_exits_2(env, monkeypatch):
    def fail(*args, **kwargs):
        raise ScanLoadError("bad file")

    monkeypatch.setattr(cli, "run", fail)
    assert cli.main([]) == cli.EXIT_LOAD_ERROR


def test_validation_error_exits_3(env, monkeypatch, capsys):
    error = cli.SummaryValidationError(["hosts[0].ip not in input"])

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(cli, "run", fail)
    assert cli.main([]) == cli.EXIT_VALIDATION_ERROR
    err = capsys.readouterr().err
    for problem in error.problems:
        assert problem in err


def test_unknown_provider_in_env_exits_4(env, monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")
    assert cli.main([]) == cli.EXIT_CONFIG_ERROR
    assert "configuration error" in capsys.readouterr().err


def test_gemini_without_key_exits_4(env, monkeypatch, capsys):
    monkeypatch.setenv("LLM_MODEL", "some-flash-model")
    assert cli.main(["--llm", "gemini"]) == cli.EXIT_CONFIG_ERROR
    assert "LLM_API_KEY" in capsys.readouterr().err
