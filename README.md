# Recon Summarization Agent

![CI](https://github.com/EricFinland/recon-summarization-agent/actions/workflows/ci.yml/badge.svg)

Environment and reconnaissance summarization component of the team project
(Anusha and Eric).

The agent reads a synthetic scan-results file (our JSON format or Nmap XML)
and produces a structured JSON summary of the hosts, ports, services, and
observations it lists, without adding anything that is not in the input.
Group 2's classification agent consumes that JSON.

This is decision support only: the agent never runs scans, never touches a
network target, and never rates risk.

## Where it fits

It is agent 1 of 4 in the team's AI-assisted penetration testing workflow,
orchestrated by a LangGraph graph on the trusted control plane:

```
 1. recon summarization   ->  2. vulnerability          ->  [human approval]  ->  3. risk            ->  4. reporting
    (this repo)               classification / CVSS                               prioritization
                              (Group 2)
```

Recon hands off directly to classification. The mandatory human approval gate
sits between classification and risk prioritization, not after recon.

## How it works

```
scan file -> load + sanitize -> summarize -> (optional LLM narrator) -> validate -> output/<scan>.summary.json -> Group 2
                                                                                 -> output/audit.log.jsonl
```

- Hosts, ports, counts, and observations are copied deterministically from the
  input. Every observation carries an `evidence` path (for example
  `hosts[0].notes[1]`) back into the scan file.
- The only free text is `overview.summary_text`, an aggregate overview of the
  whole scan (host-level detail lives in `hosts[]`). By default it comes from a
  deterministic template. Optionally an LLM (Gemini Flash or a local Ollama
  model) rewrites it from aggregate facts only (counts, services, products,
  OS guesses; no IPs or hostnames). Its text is checked against the scan and
  replaced by the template if it names a host, states a number that is not
  one of the scan's counts, or adds anything unsupported.
- Nothing is written unless the summary passes the JSON Schema and the
  "everything traces to the input" validator.

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Local (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e . --no-deps       # makes `recon_agent` importable and adds the `recon-agent` command
cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
pytest
python -m recon_agent            # summarizes data/scans/sample_scan_01.json into output/
```

Docker (no Python needed on the host):

```bash
docker compose build
docker compose run --rm recon-agent                     # sample_scan_01.json, no network, no LLM
docker compose run --rm recon-agent --input data/scans/sample_scan_03.xml --stdout
docker compose --profile llm run --rm recon-agent-llm   # LLM mode, reads .env
```

Full teammate guide (Windows and macOS/Linux, every LLM provider,
troubleshooting): [docs/SETUP.md](docs/SETUP.md).

## CLI

```
python -m recon_agent [--input FILE] [--output-dir DIR] [--llm {none,gemini,ollama}] [--stdout]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--input` | `$SCAN_INPUT_DIR/sample_scan_01.json` | Scan file (JSON or Nmap XML, detected from content) |
| `--output-dir` | `$OUTPUT_DIR` | Where `<scan stem>.summary.json` is written |
| `--llm` | `$LLM_PROVIDER` | Override the narrator provider for this run |
| `--stdout` | off | Also print the summary JSON to stdout (status lines move to stderr) |

Exit codes: `0` success, `2` scan file could not be loaded, `3` summary failed
validation (nothing written), `4` configuration error. Logs and warnings go to
stderr. `recon-agent` (installed by `pip install -e .`) is the same command.

## Configuration

Set in the environment or in `.env` (see [.env.example](.env.example)). Real
environment variables win over `.env`.

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_PROVIDER` | `none` | `none` (deterministic template), `gemini`, or `ollama` |
| `LLM_MODEL` | empty | Model name; required for `gemini` and `ollama` |
| `LLM_API_KEY` | empty | Gemini API key; required for `gemini`, never logged |
| `LLM_TIMEOUT_S` | `30` | Timeout in seconds for each LLM request (no retries) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `SCAN_INPUT_DIR` | `data/scans` | Where the default input file is looked up |
| `OUTPUT_DIR` | `output` | Where summaries are written |
| `AUDIT_LOG_PATH` | `$OUTPUT_DIR/audit.log.jsonl` | Append-only audit trail |
| `MAX_INPUT_BYTES` | `5000000` | Larger scan files are rejected before parsing |

The planned model is a Gemini Flash model (the client pays API costs, so use
the cheapest Flash tier). All data is synthetic, so a hosted model is allowed.
`none` is the default so the agent works without a key and in CI.

## Output contract (for Group 2)

| File | What it is |
|------|------------|
| [docs/OUTPUT_FORMAT.md](docs/OUTPUT_FORMAT.md) | Every field explained, guarantees, how to consume it |
| [schemas/recon_summary.schema.json](schemas/recon_summary.schema.json) | JSON Schema (draft, `schema_version` 0.2.0) |
| [schemas/examples/sample_scan_01.summary.json](schemas/examples/sample_scan_01.summary.json) | Expected output for the sample scan |
| [data/scans/sample_scan_01.json](data/scans/sample_scan_01.json) | Sample synthetic input |

Consume it as a file (`output/<scan>.summary.json`) or, inside the team's
LangGraph graph, as `state["recon_summary"]` (see `src/recon_agent/graph.py`).
Schema changes need Group 2's agreement and a `schema_version` bump.

## Security controls

| Control | Summary |
|---------|---------|
| Input validation and sanitization | Size limit, strict parsing, defusedxml for XML, invisible characters stripped |
| Prompt injection | Instruction-like notes are withheld and flagged; the LLM never sees note text; facts are screened again before any call |
| Output verification | Schema check, one-to-one check against the input, no CVE ids unless in the input, grounding check on LLM text |
| Least privilege | Reads one local file; no network unless an LLM is configured; only credential is the LLM key; container runs as non-root with no network by default |
| Audit trail | One append-only, timestamped JSON line per run (input hash, outcome, warnings, narrator use) |
| Timeouts | Every LLM request has a timeout and no retries |

Mapping to code: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#security-controls).

## Repository layout

```
.
├── src/recon_agent/
│   ├── __main__.py         CLI entry point (python -m recon_agent)
│   ├── pipeline.py         load -> summarize -> narrate -> validate -> write, plus audit event
│   ├── config.py           Settings from environment variables
│   ├── loader.py           Parse JSON or Nmap XML scan files
│   ├── sanitizer.py        Clean text, screen notes for prompt injection
│   ├── models.py           Input and output data models
│   ├── summarizer.py       Build the structured summary and template text
│   ├── validator.py        Schema check plus "everything is in the input" check
│   ├── output.py           Write JSON output for Group 2
│   ├── audit.py            Append-only audit log
│   ├── llm.py              Optional Gemini / Ollama narrator
│   ├── prompts.py          Narrator prompt text
│   └── graph.py            LangGraph node and graph (team integration point)
├── schemas/                Output contract (JSON Schema) and worked example
├── data/scans/             Synthetic scan-results input files (see data/CATALOG.md)
├── output/                 Generated summaries and audit log (gitignored)
├── tests/                  Unit, contract, CLI, and graph tests
├── docs/                   Setup, architecture, output format, tasks
├── .github/                CI workflow and PR template
├── Dockerfile
├── docker-compose.yml
├── requirements.txt        Runtime dependencies
├── requirements-dev.txt    Dev and test dependencies
└── .env.example            Environment variable template
```

## Contributing

Branch, test, open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).
