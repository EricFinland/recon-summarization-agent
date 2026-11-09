"""Configuration loaded from environment variables (and .env if present)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    llm_api_key: str
    scan_input_dir: Path
    output_dir: Path


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        scan_input_dir=Path(os.getenv("SCAN_INPUT_DIR", "data/scans")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
    )
