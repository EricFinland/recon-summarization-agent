"""LangGraph node for the recon summarization agent.

This is the integration point for the team orchestrator. The orchestrator can
either reuse `recon_node` in its own StateGraph (its state must include the
`ReconState` keys) or call `build_graph()` for a standalone recon graph.

Hand-off: the classification agent's node (Group 2) reads
`state["recon_summary"]`, a JSON-mode dict that matches
schemas/recon_summary.schema.json. Recon hands off directly; the human
approval gate sits later, between classification and risk prioritization.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from recon_agent.config import load_settings
from recon_agent.llm import build_narrator
from recon_agent.pipeline import run

RECON_NODE = "recon"


class ReconState(TypedDict, total=False):
    """Graph state keys read and written by the recon node."""

    scan_path: str
    recon_summary: dict
    recon_output_path: str
    recon_warnings: list[str]


def recon_node(state: ReconState) -> dict:
    """Summarize state["scan_path"] and return the summary, output path, and warnings."""
    scan_path = state.get("scan_path")
    if not scan_path:
        raise ValueError("recon_node needs state['scan_path'] (path to a synthetic scan file)")
    settings = load_settings()
    result = run(Path(scan_path), settings=settings, narrator=build_narrator(settings))
    return {
        "recon_summary": result.summary.model_dump(mode="json"),
        "recon_output_path": str(result.output_path),
        "recon_warnings": list(result.warnings),
    }


def build_graph() -> CompiledStateGraph:
    """Return the compiled graph START -> recon -> END."""
    graph = StateGraph(ReconState)
    graph.add_node(RECON_NODE, recon_node)
    graph.add_edge(START, RECON_NODE)
    graph.add_edge(RECON_NODE, END)
    return graph.compile()
