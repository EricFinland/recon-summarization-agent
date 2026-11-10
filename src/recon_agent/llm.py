"""Optional LLM narrator that writes `overview.summary_text`.

Providers: "none" (no LLM; the pipeline uses its deterministic template),
"gemini" (Google Gemini via google-genai), and "ollama" (a local Ollama server).

Safety rules enforced here:
- The model sees only `build_facts(summary)`: scan-wide counts and distinct
  service, product, and OS values. No note text, IP addresses, or hostnames
  are sent, because `summary_text` is an aggregate overview only.
- Before any call, every string in the facts (dict keys included) is screened
  for prompt injection. A hit raises `NarratorError`, so the pipeline falls
  back to the template.
- Every call has a timeout (settings.llm_timeout_s) and no retries.
- The API key is never logged.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

from recon_agent.config import Settings
from recon_agent.facts import aggregate_facts, fact_strings
from recon_agent.models import ReconSummary
from recon_agent.prompts import FACTS_BEGIN, FACTS_END, SYSTEM_INSTRUCTION, render_user_prompt
from recon_agent.sanitizer import looks_like_prompt_injection

if TYPE_CHECKING:
    from recon_agent.pipeline import Narrator

log = logging.getLogger(__name__)

TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 2048
# Larger scans fall back to the template instead of sending a huge prompt.
MAX_FACTS_CHARS = 20_000
MAX_NARRATIVE_CHARS = 2_000
MAX_OLLAMA_RESPONSE_BYTES = 1_000_000


class NarratorError(RuntimeError):
    """The narrator refused to call the model or got an unusable response."""


def build_facts(summary: ReconSummary) -> dict[str, Any]:
    """Return the only data the model is allowed to see.

    Aggregate counts and distinct service, product, and OS values only: no note
    text, no IP addresses, no hostnames, so the model cannot describe (or
    misdescribe) individual hosts.
    """
    return aggregate_facts(summary)


def checked_prompt(summary: ReconSummary) -> str:
    """Build the user prompt, refusing if the facts look unsafe or are too large."""
    facts = build_facts(summary)
    for text in fact_strings(facts):
        if FACTS_BEGIN in text or FACTS_END in text or looks_like_prompt_injection(text):
            raise NarratorError("scan facts contain instruction-like text; not sent to the model")
    prompt = render_user_prompt(facts)
    if len(prompt) > MAX_FACTS_CHARS:
        raise NarratorError(f"scan facts exceed {MAX_FACTS_CHARS} characters; not sent")
    return prompt


def clean_response(text: Any) -> str:
    """Collapse whitespace in model output; raise if it is empty or oversized."""
    if not isinstance(text, str):
        raise NarratorError("model returned no text")
    cleaned = " ".join(text.split())
    if not cleaned:
        raise NarratorError("model returned empty text")
    if len(cleaned) > MAX_NARRATIVE_CHARS:
        raise NarratorError(f"model output exceeds {MAX_NARRATIVE_CHARS} characters")
    return cleaned


def _gemini_narrator(settings: Settings) -> Narrator:
    """Return a narrator that calls Gemini through google-genai."""
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.llm_api_key,
        # HttpOptions.timeout is in milliseconds. No retry_options means no retries.
        http_options=types.HttpOptions(timeout=int(settings.llm_timeout_s * 1000)),
    )
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    def narrate(summary: ReconSummary) -> str:
        prompt = checked_prompt(summary)
        log.info(
            "Calling Gemini model %s (timeout %ss)", settings.llm_model, settings.llm_timeout_s
        )
        response = client.models.generate_content(
            model=settings.llm_model, contents=prompt, config=config
        )
        return clean_response(response.text)

    return narrate


def _ollama_narrator(settings: Settings) -> Narrator:
    """Return a narrator that POSTs to a local Ollama server's /api/generate."""
    host = settings.ollama_host.rstrip("/")
    if urllib.parse.urlparse(host).scheme not in ("http", "https"):
        raise ValueError(f"OLLAMA_HOST must start with http:// or https://, got {host!r}")
    url = f"{host}/api/generate"

    def narrate(summary: ReconSummary) -> str:
        body = {
            "model": settings.llm_model,
            "system": SYSTEM_INSTRUCTION,
            "prompt": checked_prompt(summary),
            "stream": False,
            "options": {"temperature": TEMPERATURE},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        log.info(
            "Calling Ollama model %s at %s (timeout %ss)",
            settings.llm_model,
            url,
            settings.llm_timeout_s,
        )
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_s) as response:
            payload = json.loads(response.read(MAX_OLLAMA_RESPONSE_BYTES))
        if not isinstance(payload, dict):
            raise NarratorError("Ollama returned an unexpected payload")
        return clean_response(payload.get("response"))

    return narrate


def build_narrator(settings: Settings) -> Narrator | None:
    """Return the narrator for settings.llm_provider, or None for "none".

    Raises ValueError when the provider is unknown or its settings are missing.
    """
    provider = settings.llm_provider
    if provider == "none":
        return None
    if provider not in ("gemini", "ollama"):
        raise ValueError(f"Unknown LLM provider {provider!r}; use none, gemini, or ollama")
    if not settings.llm_model:
        raise ValueError(f"LLM_MODEL must be set when LLM_PROVIDER={provider}")
    if settings.llm_timeout_s <= 0:
        raise ValueError("LLM_TIMEOUT_S must be greater than 0")
    if provider == "gemini":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY must be set when LLM_PROVIDER=gemini")
        return _gemini_narrator(settings)
    return _ollama_narrator(settings)
