"""Command-line entry point: python -m recon_agent (or the recon-agent script).

Exit codes: 0 success, 2 the scan file could not be loaded, 3 the summary
failed validation, 4 configuration error. Logs and warnings go to stderr.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from pathlib import Path

from recon_agent.config import LLM_PROVIDERS, load_settings
from recon_agent.llm import build_narrator
from recon_agent.loader import ScanLoadError
from recon_agent.pipeline import SummaryValidationError, run

EXIT_OK = 0
EXIT_LOAD_ERROR = 2
EXIT_VALIDATION_ERROR = 3
EXIT_CONFIG_ERROR = 4


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="recon_agent",
        description="Summarize a synthetic scan-results file into structured JSON for Group 2.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Scan file to summarize (JSON or Nmap XML). "
        "Default: SCAN_INPUT_DIR/sample_scan_01.json.",
    )
    parser.add_argument(
        "--output-dir", type=Path, help="Where to write the summary. Default: OUTPUT_DIR."
    )
    parser.add_argument("--llm", choices=LLM_PROVIDERS, help="Override LLM_PROVIDER for this run.")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Also print the summary JSON to stdout (status lines then go to stderr).",
    )
    return parser.parse_args(argv)


def _configure_logging() -> None:
    logging.basicConfig(
        stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("recon_agent").setLevel(logging.INFO)


def main(argv: list[str] | None = None) -> int:
    """Run the agent once and return a process exit code."""
    args = _parse_args(argv)
    _configure_logging()

    try:
        settings = load_settings()
        if args.llm:
            settings = dataclasses.replace(settings, llm_provider=args.llm)
        narrator = build_narrator(settings)
    except ValueError as exc:
        print(f"recon_agent: configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    input_path = args.input or settings.scan_input_dir / "sample_scan_01.json"
    try:
        result = run(input_path, args.output_dir, settings=settings, narrator=narrator)
    except ScanLoadError as exc:
        print(f"recon_agent: could not load {input_path}: {exc}", file=sys.stderr)
        return EXIT_LOAD_ERROR
    except SummaryValidationError as exc:
        print("recon_agent: summary failed validation; nothing written:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    status = sys.stderr if args.stdout else sys.stdout
    text_source = f"LLM ({settings.llm_provider})" if result.narrator_used else "template"
    print(f"Summary written to {result.output_path} (summary_text: {text_source})", file=status)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.stdout:
        print(json.dumps(result.summary.model_dump(mode="json"), indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
