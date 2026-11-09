# Tasks

Assignment: Environment and Reconnaissance Summarization (Anusha and Eric).

## Environment

- [x] Shared repository
- [x] Development environment (Python, requirements, .env template)
- [x] Basic Docker configuration (Dockerfile, docker-compose.yml)
- [x] CI: lint, tests, and Docker build on every push and PR
- [ ] Setup guide: how to install dependencies and run the prototype (docs/SETUP.md)

## Recon summarization agent

- [x] Package structure and pipeline stubs
- [x] Sample synthetic scan file (data/scans/sample_scan_01.json)
- [x] Draft output schema and worked example for Group 2
- [ ] Agree output schema with Group 2
- [ ] Pick LLM provider/model (or decide none is needed)
- [ ] `models.py`: input and output models
- [ ] `loader.py`: parse the scan file
- [ ] `summarizer.py`: build the summary
- [ ] `validator.py`: schema check plus "everything is in the input" check
- [ ] `output.py`: write JSON
- [ ] Make `tests/test_pipeline.py` pass and remove its xfail marker
- [ ] More synthetic scans with edge cases (empty scan, duplicate hosts, UDP, malformed file)

## Documentation

- [ ] docs/SETUP.md
- [ ] docs/OUTPUT_FORMAT.md
- [ ] Final README pass
