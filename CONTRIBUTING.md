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

```bash
ruff check .
ruff format .
pytest
```

CI runs the same checks plus a Docker build on every push and pull request.

## Ground rules

- Never commit `.env`, API keys, or real scan data. Only synthetic data goes in
  `data/scans/`.
- Changes to `schemas/recon_summary.schema.json` need Group 2's agreement and a
  `schema_version` bump. Update the example in `schemas/examples/` in the same PR.
- New behavior gets a test. New scan formats get a sample file in `data/scans/`.

## Commit messages

Short and imperative, for example `Add JSON loader for scan files` or
`Fix port count in overview`.
