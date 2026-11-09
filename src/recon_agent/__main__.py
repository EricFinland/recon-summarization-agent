"""Command-line entry point: python -m recon_agent [--input FILE] [--output-dir DIR]"""

import argparse
import sys
from pathlib import Path

from recon_agent.config import load_settings
from recon_agent.pipeline import run


def main(argv: list[str] | None = None) -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(prog="recon_agent", description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.scan_input_dir / "sample_scan_01.json",
        help="Scan-results file to summarize.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.output_dir,
        help="Directory to write the summary JSON into.",
    )
    args = parser.parse_args(argv)

    try:
        out = run(args.input, args.output_dir)
    except NotImplementedError:
        print(f"recon_agent: pipeline not implemented yet (input: {args.input})")
        return 1
    print(f"Summary written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
