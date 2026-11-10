# Setup Guide

How to install the recon summarization agent, run it, and add new synthetic
scans. Commands are given for Windows PowerShell and for macOS/Linux (bash or
zsh) where they differ.

## 1. Prerequisites

| Tool | Version | Needed for |
|------|---------|------------|
| Git | any recent | cloning the repo |
| Python | 3.11 or newer (CI tests 3.11 and 3.12) | running locally |
| Docker Desktop (or Docker Engine with Compose v2.24+) | recent | running in a container (optional) |
| Ollama | recent | only if you want a local LLM (optional) |

You do not need an API key. The default `LLM_PROVIDER=none` uses a
deterministic template and works offline.

## 2. Clone the repo

The repo is private; ask Eric for access first.

```bash
git clone https://github.com/EricFinland/recon-summarization-agent.git
cd recon-summarization-agent
```

## 3. Create a virtual environment and install

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e . --no-deps
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e . --no-deps
cp .env.example .env
```

`pip install -e . --no-deps` installs the package in editable mode, so
`import recon_agent` works from anywhere and the `recon-agent` command exists.
Keep it editable: the validator finds `schemas/` relative to the source tree.

## 4. Configure `.env`

`.env` is gitignored. Never commit it. The defaults are fine for a first run.
See [the configuration table in the README](../README.md#configuration) for
every variable. Real environment variables take precedence over `.env`.

## 5. Run the tests and linters

```bash
pytest
ruff check .
ruff format --check .      # or `ruff format .` to fix formatting
```

Tests never touch the network: the Gemini client and the Ollama HTTP call are
mocked, and CLI/graph tests force `LLM_PROVIDER=none`.

## 6. Run the agent

### No LLM (default)

```bash
python -m recon_agent                                            # data/scans/sample_scan_01.json
python -m recon_agent --input data/scans/sample_scan_02.json     # prompt-injection and edge cases
python -m recon_agent --input data/scans/sample_scan_03.xml      # Nmap XML
python -m recon_agent --input data/scans/sample_scan_01.json --stdout   # also print the JSON
```

Output goes to `output/<scan stem>.summary.json`. Each run also appends one
line to `output/audit.log.jsonl`. Warnings (for example "narrator text
rejected") are printed to stderr and recorded in the audit log.

Exit codes: `0` ok, `2` scan file could not be loaded, `3` summary failed
validation (nothing written), `4` configuration error.

### Gemini (hosted, planned model)

1. Create an API key in Google AI Studio (https://aistudio.google.com). The
   client pays for usage, so use the cheapest Flash model.
2. Check AI Studio for the current Flash model name (names change; the
   example in `.env.example` may be out of date).
3. In `.env`:

   ```
   LLM_PROVIDER=gemini
   LLM_MODEL=<current Flash model name>
   LLM_API_KEY=<your key>
   ```

4. Run `python -m recon_agent`, or keep `.env` on `none` and use
   `python -m recon_agent --llm gemini` for a single run.

The status line says `summary_text: LLM (gemini)` when the model's text passed
the grounding check, or `summary_text: template` plus a warning when it did
not (or the call failed or timed out).

### Ollama (local)

1. Install Ollama and pull a model, for example `ollama pull llama3.2`.
2. Make sure it is running (`ollama serve`, or the desktop app).
3. In `.env`: `LLM_PROVIDER=ollama`, `LLM_MODEL=llama3.2`, and
   `OLLAMA_HOST=http://localhost:11434`.
4. Run `python -m recon_agent` (or `--llm ollama`).

## 7. Run with Docker

```bash
docker compose build
docker compose run --rm recon-agent
docker compose run --rm recon-agent --input data/scans/sample_scan_03.xml --stdout
```

The default `recon-agent` service has no network (`network_mode: none`),
forces `LLM_PROVIDER=none`, runs as a non-root user with a read-only root
filesystem, mounts `./data` read-only, and writes to `./output`. Arguments
after the service name are passed to the CLI.

LLM mode uses the `recon-agent-llm` service, which has network access and
reads `.env`:

```bash
docker compose --profile llm run --rm recon-agent-llm
```

For Ollama on your machine, set `OLLAMA_HOST=http://host.docker.internal:11434`
in `.env` (inside a container, `localhost` is the container itself).

Without Compose:

```bash
docker build -t recon-agent .
docker run --rm --network none -v "$PWD/output:/app/output" recon-agent
```

(PowerShell: use `${PWD}` in place of `$PWD`.)

## 8. Use it from LangGraph

```python
from recon_agent.graph import build_graph

state = build_graph().invoke({"scan_path": "data/scans/sample_scan_01.json"})
state["recon_summary"]  # dict matching schemas/recon_summary.schema.json
state["recon_output_path"]  # where the JSON was written
state["recon_warnings"]  # list of warnings (empty when all is well)
```

The team orchestrator can add `recon_agent.graph.recon_node` to its own
`StateGraph` instead; see [ARCHITECTURE.md](ARCHITECTURE.md#langgraph-integration).

## 9. Add a new synthetic scan

Only synthetic data goes in this repo. Never commit real scan output.

1. Create `data/scans/sample_scan_NN_<what_it_tests>.json` (or `.xml` for Nmap
   `-oX` output). Use documentation or private address ranges
   (`10.0.0.0/8`, `192.168.0.0/16`, `192.0.2.0/24`, `2001:db8::/32`) and
   `.lab.local` hostnames. Copy `sample_scan_01.json` as a starting point.
2. Run it: `python -m recon_agent --input data/scans/<file> --stdout`. It must
   exit 0 (or, for an intentionally broken file, 2 with a clear message).
3. Add an entry to `data/CATALOG.md`: file name, format, and what edge cases
   it covers.
4. If the file is a contract example for Group 2, save the reviewed output as
   `schemas/examples/<scan stem>.summary.json` and set `generated_at` to a
   fixed value. Read it line by line against the input: every value must come
   from the scan.
5. Add or extend a test in `tests/` that exercises the new case.

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| PowerShell: "running scripts is disabled on this system" when activating | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat` from cmd |
| `ModuleNotFoundError: No module named 'recon_agent'` | Activate the venv and run `pip install -e . --no-deps` from the repo root. `pytest` works without it (pyproject adds `src` to the path) |
| Exit code 4, `configuration error` | `LLM_PROVIDER` is not `none`/`gemini`/`ollama`, or `LLM_MODEL` / `LLM_API_KEY` is missing for the chosen provider. Check `.env` and real environment variables |
| `summary_text: template` with a "narrator failed" warning | The LLM call failed or timed out (`LLM_TIMEOUT_S`). Check the key, model name, network, or that Ollama is running. The summary is still valid |
| "narrator text rejected" warning | The model mentioned something not in the scan (an IP, port, version, CVE, or a risk word), named an individual host, or stated a number that is not one of the scan's counts. Working as intended; the template text was kept |
| Exit code 2 | The scan file is missing, too large (`MAX_INPUT_BYTES`), not UTF-8, malformed, or fails the input model. The message says which |
| Exit code 3 | The summary failed validation. This is a bug in the agent; open an issue with the input file |
| Docker on Linux: `Permission denied` writing `output/` | The container runs as uid 10001. Run `RECON_UID=$(id -u) RECON_GID=$(id -g) docker compose run --rm recon-agent`, or `chmod 777 output` |
| Docker: Ollama not reachable | Use `OLLAMA_HOST=http://host.docker.internal:11434` and the `recon-agent-llm` service (the default service has no network) |
| `ruff format --check` fails in CI but not locally | Install the pinned version: `pip install -r requirements-dev.txt` |
| Tests pick up your `.env` settings | Tests set every relevant variable explicitly; if one still leaks, report it |
