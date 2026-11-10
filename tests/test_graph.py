"""LangGraph integration: the recon graph runs end to end and hands off a schema-valid summary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from recon_agent import graph as recon_graph
from recon_agent.models import ReconSummary


@pytest.fixture
def env(tmp_path, monkeypatch) -> Path:
    """Point every setting at tmp_path so a developer's .env cannot leak into the test."""
    out = tmp_path / "out"
    for key, value in {
        "LLM_PROVIDER": "none",
        "LLM_MODEL": "",
        "LLM_API_KEY": "",
        "OUTPUT_DIR": str(out),
        "AUDIT_LOG_PATH": str(tmp_path / "audit.log.jsonl"),
    }.items():
        monkeypatch.setenv(key, value)
    return out


def test_graph_runs_on_sample_scan(env, sample_scan_path, schema):
    state = recon_graph.build_graph().invoke({"scan_path": str(sample_scan_path)})

    assert list(Draft202012Validator(schema).iter_errors(state["recon_summary"])) == []
    assert state["recon_summary"]["overview"]["hosts_total"] == 5
    assert Path(state["recon_output_path"]) == env / "sample_scan_01.summary.json"
    assert isinstance(state["recon_warnings"], list)


def test_node_maps_run_result_into_state(env, monkeypatch, expected_summary):
    summary = ReconSummary.model_validate(expected_summary)
    seen: dict = {}

    def fake_run(path, *args, **kwargs):
        seen["path"], seen["narrator"] = path, kwargs.get("narrator")
        return SimpleNamespace(
            summary=summary, output_path=Path("out/x.summary.json"), warnings=["w1"]
        )

    monkeypatch.setattr(recon_graph, "run", fake_run)
    update = recon_graph.recon_node({"scan_path": "data/scans/x.json"})

    assert seen == {"path": Path("data/scans/x.json"), "narrator": None}
    assert update["recon_summary"] == summary.model_dump(mode="json")
    assert update["recon_output_path"] == str(Path("out/x.summary.json"))
    assert update["recon_warnings"] == ["w1"]


def test_node_requires_scan_path(env):
    with pytest.raises(ValueError, match="scan_path"):
        recon_graph.recon_node({})
