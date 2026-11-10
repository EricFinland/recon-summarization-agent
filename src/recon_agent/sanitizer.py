"""Clean scan text and screen scan notes for prompt injection.

Scan files are untrusted: a banner, HTTP title, or certificate field is
whatever the scanned host chose to send, so an attacker can plant text aimed
at any AI model that later reads the scan. This module is one of two layers
of defense:

1. Heuristic screening (this module). `looks_like_prompt_injection` flags
   notes that read like instructions to an AI model, and `check_note` withholds
   the text of any flagged note. It is a best-effort pattern match, not a
   guarantee: it will miss novel phrasings and homoglyph tricks.
2. Structural isolation (summarizer and prompts). Hosts, ports, and
   observations are copied deterministically, and the optional LLM only
   receives counts and structured facts. It never sees raw note text, so a
   note that slips past layer 1 still cannot reach a model as instructions.

`clean_text` also removes invisible characters (zero-width, bidi overrides,
Unicode tag characters, control characters) that are commonly used to hide
payloads from human reviewers.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from recon_agent.models import (
    WITHHELD_NOTE_TEXT,
    ObservationFlag,
    ScanHost,
    ScanPort,
    ScanResult,
)

MAX_NOTE_CHARS = 500

# Unicode categories removed outright: control (Cc), format (Cf: zero-width
# characters, bidi overrides, BOM, tag characters), and lone surrogates (Cs).
# Whitespace control characters such as tab and newline become a space instead.
_REMOVED_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})


def clean_text(value: str) -> str:
    """Return `value` NFKC-normalized, without invisible characters, whitespace collapsed."""
    kept = []
    for char in value:
        if char.isspace():
            kept.append(" ")
        elif unicodedata.category(char) not in _REMOVED_CATEGORIES:
            kept.append(char)
    normalized = unicodedata.normalize("NFKC", "".join(kept))
    return " ".join(normalized.split())


# --------------------------------------------------------------------------
# Prompt-injection heuristic
# --------------------------------------------------------------------------

# Words that refer to an AI model when someone addresses it directly. A bare
# "model" is left out because notes often mention device or product models.
_AI_NOUN = (
    r"(?:ai|llm|gpt|chatgpt|chatbot|(?:ai|language)\W+model|assistant|summari[sz]er"
    r"|classifier|copilot)"
)

# Each pattern runs against the cleaned, lowercased note. `\W+` between words
# tolerates extra spaces and punctuation.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        # "ignore all previous instructions", "disregard the above rules", ...
        r"\b(?:ignore|disregard|forget|override|bypass)\W+(?:(?:all|any|every|the|your|my|these"
        r"|those|of|previous|prior|above|earlier|preceding|former|system|original|existing"
        r"|safety)\W+){0,4}(?:instructions?|prompts?|rules|directions|directives|guidance"
        r"|guidelines|context|messages?|commands?)\b",
        # "system prompt", "reveal your instructions"
        r"\bsystem\W*prompt\b",
        r"\b(?:reveal|print|show|repeat|output)\W+(?:\w+\W+){0,2}?(?:your|the)\W+(?:\w+\W+)?"
        r"(?:prompt|instructions)\b",
        # Role changes: "you are now ...", "pretend to be ...", "from now on, you ..."
        r"\byou\W+are\W+now\b",
        r"\bpretend\W+(?:to\W+be|you\W+are)\b",
        r"\bfrom\W+now\W+on\W+you\b",
        # Role tags at the start of the text or of a sentence: "system:", "assistant:"
        r"(?:^|[.;!?>\]\)}|]\s*)(?:system|assistant)\s*:",
        r"[\[<]\s*/?\s*(?:system|assistant|inst)\s*[\]>]",
        r"#{2,}\s*(?:system|instruction|instructions|assistant)\b",
        # Chat-template tokens: <|im_start|>, <|endoftext|>, [INST], <<SYS>>, <start_of_turn>
        r"<\|[a-z_]+\|>",
        r"\[/?inst\]",
        r"<</?sys>>",
        r"</?(?:start|end)_of_turn>",
        # Output steering at the start of a sentence: "Respond only with ..."
        r"(?:^|[.!?:;]\s*)(?:please\W+)?(?:respond|reply|answer)\W+(?:only\W+)?with\b",
        r"\bin\W+your\W+(?:response|reply|answer|summary|report|output)\b",
        # Suppression: "do not report", "don't mention", "never flag"
        r"\b(?:do\W+not|don\W?t|never)\W+(?:report|mention|flag|include|list|disclose|reveal"
        r"|output|log|alert)\b",
        # Verdict steering: "mark this host as safe", "report no vulnerabilities"
        r"\b(?:mark|classify|label|treat|flag|categori[sz]e|consider)\W+(?:\w+\W+){0,6}?as\W+"
        r"(?:safe|secure|clean|benign|harmless|low\W+risk|informational|false\W+positives?"
        r"|not\W+vulnerable)\b",
        r"\b(?:report|say|conclude|claim|output)\s+(?:that\s+)?(?:(?:this|the)\s+\w+\s+has\s+"
        r"|there\s+(?:are|were|is)\s+)?(?:no|zero)\s+(?:vulnerabilit(?:y|ies)|issues|findings"
        r"|risks?|problems)\b",
        # Fabrication requests: "invent a CVE", "make up findings"
        r"\b(?:invent|fabricate|make\W+up|hallucinate)\W+(?:\w+\W+){0,3}?(?:cves?"
        r"|vulnerabilit(?:y|ies)|findings?|evidence)\b",
        # "new instructions", "updated instructions"
        r"\b(?:new|updated|revised|real|actual|true)\W+(?:instructions?|directives?|orders)\b",
        # Addressing an AI directly: "Note to the AI", "Hey assistant", "if you are an LLM"
        rf"\b(?:dear|hey|hi|hello|attention|note\W+to|message\W+to|instructions?\W+for)\W+"
        rf"(?:the\W+|any\W+|all\W+)?(?:\w+\W+){{0,2}}?{_AI_NOUN}s?\b",
        rf"\bif\W+you\W+are\W+(?:an?\W+)?(?:\w+\W+)?(?:{_AI_NOUN}|model)\b",
        r"\bas\W+an?\W+(?:ai|llm|language\W+model)\b",
        rf"\b{_AI_NOUN}s?\W+(?:reading|processing|summari[sz]ing|analy[sz]ing|parsing)\W+this\b",
        r"\bjailbreak",
    )
)

# Letters-only form, to catch spaced or punctuated spellings such as
# "i g n o r e  a.l.l  previous instructions".
_SQUASHED_PATTERN = re.compile(
    r"(?:ignore|disregard|forget)(?:all|any|the|your|of)*(?:previous|prior|above|earlier)?"
    r"(?:instructions|instruction|prompts|prompt)"
)


def looks_like_prompt_injection(text: str) -> bool:
    """Return True if `text` reads like instructions aimed at an AI model.

    Case-insensitive and applied to the cleaned text, so invisible characters
    and extra spacing do not hide a match. This is the heuristic first layer
    described in the module docstring.
    """
    lowered = clean_text(text).casefold()
    if any(pattern.search(lowered) for pattern in _INJECTION_PATTERNS):
        return True
    squashed = re.sub(r"[^a-z]", "", lowered)
    return _SQUASHED_PATTERN.search(squashed) is not None


@dataclass(frozen=True)
class NoteCheck:
    """Text to publish for a scan note, plus the flags explaining any change."""

    text: str
    flags: tuple[ObservationFlag, ...]


def check_note(note: str) -> NoteCheck:
    """Withhold a note that looks like prompt injection, or truncate one that is too long."""
    if looks_like_prompt_injection(note):
        return NoteCheck(text=WITHHELD_NOTE_TEXT, flags=("possible_prompt_injection",))
    if len(note) > MAX_NOTE_CHARS:
        return NoteCheck(text=note[:MAX_NOTE_CHARS], flags=("truncated",))
    return NoteCheck(text=note, flags=())


# --------------------------------------------------------------------------
# Whole-scan cleaning
# --------------------------------------------------------------------------


def _clean_optional(value: str | None) -> str | None:
    """Clean an optional field; a value that becomes empty turns into None."""
    if value is None:
        return None
    return clean_text(value) or None


def _sanitize_port(port: ScanPort) -> ScanPort:
    return port.model_copy(
        update={
            "service": _clean_optional(port.service),
            "product": _clean_optional(port.product),
            "version": _clean_optional(port.version),
        }
    )


def _sanitize_host(host: ScanHost) -> ScanHost:
    return host.model_copy(
        update={
            "hostname": _clean_optional(host.hostname),
            "os_guess": _clean_optional(host.os_guess),
            "ports": [_sanitize_port(port) for port in host.ports],
            # Empty notes stay in place so evidence indexes match the input file.
            "notes": [clean_text(note) for note in host.notes],
        }
    )


def sanitize_scan(scan: ScanResult) -> ScanResult:
    """Return a copy of `scan` with every string field cleaned by `clean_text`.

    Nothing is truncated or withheld here, so list positions (and therefore
    evidence paths like hosts[0].notes[1]) stay identical to the input file.
    """
    return scan.model_copy(
        update={
            "scan_id": _clean_optional(scan.scan_id),
            "scanner": _clean_optional(scan.scanner),
            "scan_type": _clean_optional(scan.scan_type),
            "target_range": _clean_optional(scan.target_range),
            "hosts": [_sanitize_host(host) for host in scan.hosts],
        }
    )
