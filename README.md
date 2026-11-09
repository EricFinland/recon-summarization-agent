# Recon Summarization Agent

![CI](https://github.com/EricFinland/recon-summarization-agent/actions/workflows/ci.yml/badge.svg)

Environment and reconnaissance summarization component of the team project
(Anusha and Eric).

The agent reads a synthetic scan-results file and produces a structured JSON
summary of the listed hosts, ports, services, and observations, without adding
information that is not in the input. Group 2's classification agent consumes
that JSON.

> **Status:** environment and scaffolding are done; the agent itself is not
> implemented yet. See [docs/TASKS.md](docs/TASKS.md) for what is left.

## How it works

```
data/scans/*.json  ->  load  ->  summarize  ->  validate  ->  output/*.summary.json  ->  Group 2
```

Every fact in the output must trace back to the input. Observations carry an
`evidence` path into the scan file, and the validator rejects anything it
cannot find there. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

Local (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e . --no-deps       # makes `recon_agent` importable from anywhere
cp .env.example .env
pytest
python -m recon_agent --input data/scans/sample_scan_01.json
```

Docker:

```bash
docker compose build
docker compose run --rm recon-agent
docker compose run --rm recon-agent python -m recon_agent --input data/scans/sample_scan_01.json
```

Full setup instructions: [docs/SETUP.md](docs/SETUP.md).

## Output contract (for Group 2)

| File | What it is |
|------|------------|
| [schemas/recon_summary.schema.json](schemas/recon_summary.schema.json) | JSON Schema for the output (draft v0.1.0) |
| [schemas/examples/sample_scan_01.summary.json](schemas/examples/sample_scan_01.summary.json) | Expected output for the sample scan |
| [data/scans/sample_scan_01.json](data/scans/sample_scan_01.json) | Sample synthetic input |

`tests/test_contract.py` checks that these three stay consistent. Schema
changes need Group 2's agreement and a `schema_version` bump.

## Repository layout

```
.
├── src/recon_agent/
│   ├── __main__.py         CLI entry point (python -m recon_agent)
│   ├── pipeline.py         load -> summarize -> validate -> write
│   ├── config.py           Settings from environment variables
│   ├── loader.py           Parse the scan-results file
│   ├── models.py           Input and output data models
│   ├── prompts.py          LLM prompt templates
│   ├── summarizer.py       Build the structured summary
│   ├── validator.py        Check the summary is fully supported by the input
│   └── output.py           Write JSON output for Group 2
├── schemas/                Output contract (JSON Schema) and worked examples
├── data/scans/             Synthetic scan-results input files
├── output/                 Generated summaries (gitignored)
├── tests/                  Contract tests, CLI test, golden pipeline test
├── docs/                   Architecture, tasks, setup, output format
├── .github/                CI workflow and PR template
├── Dockerfile
├── docker-compose.yml
├── requirements.txt        Runtime dependencies
├── requirements-dev.txt    Dev and test dependencies
└── .env.example            Environment variable template
```

## Contributing

Branch, test, open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).
