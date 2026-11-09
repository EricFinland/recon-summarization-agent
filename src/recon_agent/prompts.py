"""Prompt templates for the summarization step (if an LLM is used).

Guidelines for prompts written here:
- Give the model only the parsed scan data, nothing else.
- Tell it to restate, never infer (no guessing versions, OS, or vulnerabilities).
- Ask for JSON that matches the schema, then validate it before using it.

TODO: add prompt templates.
"""
