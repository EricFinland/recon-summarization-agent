# Recon Summarization Agent

Environment and reconnaissance summarization component of the team project
(Anusha and Eric).

The agent reads a synthetic scan-results file and produces a structured
summary of the listed hosts, ports, services, and observations, without adding
information that is not in the input. Its output is consumed by Group 2's
classification agent.

> Status: scaffolding only. Nothing is implemented yet.

## Repository layout

```
.
├── src/recon_agent/        Agent package
│   ├── __main__.py         CLI entry point (python -m recon_agent)
│   ├── config.py           Settings from environment variables
│   ├── loader.py           Parse the scan-results file
│   ├── models.py           Input and output data models
│   ├── prompts.py          LLM prompt templates
│   ├── summarizer.py       Build the structured summary
│   ├── validator.py        Check the summary is fully supported by the input
│   └── output.py           Write JSON output for Group 2
├── schemas/                Output contract (JSON Schema) shared with Group 2
├── data/scans/             Synthetic scan-results input files
├── output/                 Generated summaries (gitignored)
├── tests/                  Pytest tests
├── docs/                   Setup and design docs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt        Runtime dependencies
├── requirements-dev.txt    Dev and test dependencies
└── .env.example            Environment variable template
```

## Quick start

Local (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest
PYTHONPATH=src python -m recon_agent
```

Docker:

```bash
docker compose build
docker compose run --rm recon-agent
```

Full setup instructions: see [docs/SETUP.md](docs/SETUP.md).

## Output contract

The structured output format lives in
[schemas/recon_summary.schema.json](schemas/recon_summary.schema.json).
It is the interface with Group 2, so coordinate with them before changing it.
