# Contributing

## Workflow

1. Pull the latest `main`.
2. Create a branch: `git checkout -b <your-name>/<short-description>`
   (for example `eric/loader`).
3. Make your change with tests.
4. Run the checks below before pushing.
5. Open a pull request into `main` and ask your teammate to review.

Keep `main` working: CI must pass before merging.

## Checks

With the virtual environment active (see [docs/SETUP.md](docs/SETUP.md)):

```bash
ruff check .
ruff format --check .     # `ruff format .` fixes formatting
pytest
```

CI runs the same checks on Python 3.11 and 3.12, then builds the Docker image,
runs it with no network, and validates the summary it writes. `ruff` is pinned
in `requirements-dev.txt` so formatting matches CI.

## Ground rules

- Never commit `.env`, API keys, or real scan data. Only synthetic data goes in
  `data/scans/`, and every new scan gets an entry in `data/CATALOG.md`.
- Tests must never touch the network. Mock the Gemini client and the Ollama
  HTTP call; CLI and graph tests use `LLM_PROVIDER=none`.
- Changes to `schemas/recon_summary.schema.json` need Group 2's agreement and a
  `schema_version` bump. Update the example in `schemas/examples/` and
  `docs/OUTPUT_FORMAT.md` in the same PR.
- New behavior gets a test. New scan formats get a sample file in `data/scans/`.
- Keep `requirements.txt` and `[project] dependencies` in `pyproject.toml` in
  sync.

## Commit messages

Short and imperative, for example `Add JSON loader for scan files` or
`Fix port count in overview`.
