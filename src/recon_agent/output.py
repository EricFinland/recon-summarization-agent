"""Write the structured summary to disk for Group 2 to consume."""

import json
import os
import tempfile
from pathlib import Path

from recon_agent.models import ReconSummary


def write_output(summary: ReconSummary, output_dir: Path, scan_file: str) -> Path:
    """Write `summary` to `<output_dir>/<scan_file stem>.summary.json` and return the path.

    The file is pretty-printed UTF-8 JSON with a trailing newline. It is written
    to a temporary file in the same directory and then moved into place, so a
    reader never sees a partially written summary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{Path(scan_file).stem}.summary.json"
    payload = json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=output_dir, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return target
