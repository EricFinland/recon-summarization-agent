# Tasks

Assignment: Environment and Reconnaissance Summarization (Anusha and Eric).

## Environment

- [x] Shared repository
- [x] Development environment (Python, requirements, .env template)
- [x] Docker configuration (non-root image; compose with a no-network default service and an LLM profile)
- [x] CI: lint, format check, and tests on Python 3.11 and 3.12; Docker build and container smoke test that validates the output
- [x] Setup guide: how to install dependencies and run the prototype (docs/SETUP.md)

## Recon summarization agent

- [x] Package structure and pipeline
- [x] Synthetic scans: sample 01 (baseline), 02 (prompt injection and edge cases), 03 (Nmap XML), 04 (empty), catalogued in data/CATALOG.md
- [x] Draft output schema (0.2.0) and worked example for Group 2
- [x] `models.py`: input and output models
- [x] `loader.py`: parse JSON and Nmap XML scan files safely
- [x] `sanitizer.py`: clean text and screen notes for prompt injection
- [x] `summarizer.py`: build the summary and the template overview text
- [x] `validator.py`: schema check, "everything is in the input" check, grounding check for free text
- [x] `output.py`: write JSON atomically
- [x] `audit.py`: append-only audit log
- [x] `llm.py` and `prompts.py`: optional Gemini / Ollama narrator with injection screening and timeouts
- [x] `graph.py`: LangGraph node and graph for the team orchestrator
- [x] CLI with documented exit codes
- [ ] Agree output schema with Group 2
- [ ] Pick the exact Gemini Flash model name and try it with the client's key (code and mocked tests are done)
- [ ] Wire `recon_node` into the team orchestrator graph together with Group 2's classification node

## Documentation

- [x] docs/SETUP.md
- [x] docs/OUTPUT_FORMAT.md
- [x] docs/ARCHITECTURE.md (pipeline, LangGraph integration, security controls)
- [x] Final README pass
