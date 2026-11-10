"""Configuration loaded from environment variables (and .env if present)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# "none" means no LLM: summary_text comes from a deterministic template.
LLM_PROVIDERS = ("none", "gemini", "ollama")


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "none"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_s: float = 30.0
    ollama_host: str = "http://localhost:11434"
    scan_input_dir: Path = Path("data/scans")
    output_dir: Path = Path("output")
    audit_log_path: Path = Path("output/audit.log.jsonl")
    max_input_bytes: int = 5_000_000


def load_settings() -> Settings:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "none").strip().lower() or "none"
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {LLM_PROVIDERS}, got {provider!r}")
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    return Settings(
        llm_provider=provider,
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        scan_input_dir=Path(os.getenv("SCAN_INPUT_DIR", "data/scans")),
        output_dir=output_dir,
        audit_log_path=Path(os.getenv("AUDIT_LOG_PATH", str(output_dir / "audit.log.jsonl"))),
        max_input_bytes=int(os.getenv("MAX_INPUT_BYTES", "5000000")),
    )
