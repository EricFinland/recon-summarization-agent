# Output Format (for Group 2)

The recon agent produces one JSON document per scan file. This page explains
every field, what we guarantee about it, and how to consume it.

- Schema (source of truth): [schemas/recon_summary.schema.json](../schemas/recon_summary.schema.json)
- Worked example: [schemas/examples/sample_scan_01.summary.json](../schemas/examples/sample_scan_01.summary.json),
  built from [data/scans/sample_scan_01.json](../data/scans/sample_scan_01.json)
- Current `schema_version`: `0.2.0` (draft, not yet agreed with Group 2)

## Top level

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | string, always `"0.2.0"` | Version of this contract. Check it before reading anything else |
| `generated_at` | string, ISO 8601 date-time in UTC (e.g. `2026-11-01T14:10:00Z`) | When the agent produced the summary. Not when the scan ran |
| `source` | object | Which input file the summary describes |
| `overview` | object | Counts and a short plain-language overview |
| `hosts` | array of host objects | One entry per host in the input, in input order |

No other keys appear (`additionalProperties: false` everywhere).

## `source`

| Field | Type | Meaning |
|-------|------|---------|
| `scan_file` | string | Bare file name of the input (no directories), e.g. `sample_scan_01.json` |
| `scan_id` | string or null | `scan_id` from the input; null if the input has none (always null for Nmap XML) |
| `target_range` | string or null | Scanned range from the input; null if absent (always null for Nmap XML). The schema marks it optional, but this agent always emits it |

## `overview`

| Field | Type | Meaning |
|-------|------|---------|
| `hosts_total` | integer >= 0 | Number of hosts in the input (equals `len(hosts)`) |
| `hosts_up` | integer >= 0 | Hosts with `status` `"up"` |
| `open_ports_total` | integer >= 0 | Sum of `len(open_ports)` over all hosts |
| `summary_text` | string | Short plain-language overview of the whole scan, for humans. Do not parse it; use the structured fields |

`summary_text` comes from a deterministic template unless an LLM narrator is
configured and its text passes the grounding check (see Guarantees). Either
way it is an aggregate overview only: counts, services, products, and OS
guesses for the scan as a whole. It never names individual hosts (host-level
detail is in `hosts[]`) and never contains severity, risk, or exploit language
unless the scan itself uses those words.

## `hosts[]`

| Field | Type | Meaning |
|-------|------|---------|
| `ip` | string | IPv4 or IPv6 address, copied from the input (validated as an IP) |
| `hostname` | string or null | Copied from the input; null if none |
| `status` | `"up"`, `"down"`, or `"unknown"` | Host state reported by the scan |
| `os_guess` | string or null | The scanner's OS guess, copied as is; null if the input has none. Never inferred by us |
| `open_ports` | array | Ports in state `open`, in input order |
| `other_ports` | array | Every port not in state `open` (closed, filtered, ...), in input order, so nothing is silently dropped |
| `observations` | array | One entry per non-empty scan note for this host, in note order |

Hosts that are down are still listed (with empty arrays if the input has
nothing for them).

### `open_ports[]`

| Field | Type | Meaning |
|-------|------|---------|
| `port` | integer 0 to 65535 | Port number |
| `protocol` | `"tcp"` or `"udp"` | Transport protocol |
| `service` | string or null | Service name from the scan (e.g. `ssh`); null if the scan has none |
| `product` | string or null | Product from the scan (e.g. `OpenSSH`); null if none |
| `version` | string or null | Version string from the scan (e.g. `8.9p1`); null if none. Never guessed |

### `other_ports[]`

| Field | Type | Meaning |
|-------|------|---------|
| `port` | integer 0 to 65535 | Port number |
| `protocol` | `"tcp"` or `"udp"` | Transport protocol |
| `state` | `"closed"`, `"filtered"`, `"open\|filtered"`, or `"unknown"` | State from the scan. Nmap states outside this list (e.g. `closed\|filtered`) become `"unknown"` |
| `service` | string or null | Service name from the scan; null if none |

### `observations[]`

| Field | Type | Meaning |
|-------|------|---------|
| `text` | string | The scan note, cleaned (see below). Not reworded |
| `evidence` | string | Where the note is in the input, e.g. `hosts[0].notes[1]` |
| `flags` | array of unique strings | Empty for a normal note; see Flags |

## Flags

| Flag | Meaning | What `text` contains |
|------|---------|----------------------|
| `possible_prompt_injection` | The note read like instructions aimed at an AI model (for example "ignore all previous instructions") | A fixed placeholder: "Note withheld from summary: it contains instruction-like text. Review the raw scan file at the evidence path." The original text is not included |
| `truncated` | The note was longer than 500 characters | The first 500 characters |

A withheld note may itself be a meaningful finding (someone planted text in a
banner). If Group 2 wants to surface it, use the `evidence` path to show a
human the raw file; never pass the raw text to a model as instructions.

## Evidence path format

`hosts[N].notes[M]`, where `N` and `M` are zero-based indexes:

- `N` is the host's position in the input file's host list (same as its
  position in the output `hosts` array).
- `M` is the note's position in that host's `notes` list in the input file.
  Empty notes are skipped (no observation), but indexes are not renumbered, so
  `M` always points at the original note.
- For Nmap XML input, `N` follows the order of `<host>` elements and `M`
  follows the loader's note order: each port's `<script>` output (as
  `"<port>/<protocol> <script id>: <output>"`) in port order, then each
  `<hostscript>` script (as `"<script id>: <output>"`).

## Text cleaning

All strings from the input are cleaned before use: Unicode NFKC
normalization, removal of control and invisible format characters
(zero-width spaces, bidi overrides, tag characters), and whitespace collapsed
to single spaces. So `"web02​.lab.local"` in the input becomes
`"web02.lab.local"` in the output. Values are otherwise unchanged.

## Guarantees

Checked by `validator.py` before the file is written; if any check fails,
nothing is written and the run exits with code 3.

1. The document matches the JSON Schema for its `schema_version`.
2. Every fact traces to the input: hosts match the input one to one and in
   order; `ip`, `hostname`, `status`, and `os_guess` equal the (cleaned) input
   values; ports match the input exactly; overview counts match the input.
3. Every observation's `evidence` resolves to a non-empty input note, every
   non-empty note has exactly one observation, and `text` and `flags` are what
   the note rules above produce.
4. No CVE identifier appears unless the same identifier is in the input. (A
   CVE id that is in a scan note passes through as observation text.)
5. `summary_text` is an aggregate overview. It mentions no IP address, port,
   version, hostname, or CVE id that is not in the input, and no host's IP
   address or hostname at all (the scan's `target_range` may appear). Every
   number in it (digits, or the words zero to twenty) is one of the scan's
   aggregate counts, or a scan port in a port context, and simple status
   claims such as "4 of 5 hosts are up" must match the input. It contains no
   risk words (vulnerable, exploit, CVSS, severity, critical, compromise,
   malware, backdoor) unless the input uses them. An LLM's text that fails
   this is discarded and the template is used. The check is lexical and
   numeric, so it cannot prove every sentence is true: read facts from the
   structured fields, never from `summary_text`.
6. No severity, risk score, or priority fields exist. Classification and
   scoring are Group 2's job.

Not guaranteed: that the scan itself is accurate or complete. We summarize
what the synthetic scan says, nothing more.

## How to consume it

### As a file

The agent writes `output/<scan stem>.summary.json` (pretty-printed UTF-8,
written atomically, so you never read a half-written file).

```python
import json
from jsonschema import Draft202012Validator

schema = json.load(open("schemas/recon_summary.schema.json", encoding="utf-8"))
summary = json.load(open("output/sample_scan_01.summary.json", encoding="utf-8"))
assert summary["schema_version"] == "0.2.0"
Draft202012Validator(schema).validate(summary)

for host in summary["hosts"]:
    for port in host["open_ports"]:
        print(host["ip"], port["port"], port["protocol"], port["product"], port["version"])
```

### In the LangGraph graph

`recon_agent.graph.recon_node` reads `state["scan_path"]` and writes:

| State key | Type | Content |
|-----------|------|---------|
| `recon_summary` | dict | This document, as JSON-compatible Python values |
| `recon_output_path` | str | Path of the written file |
| `recon_warnings` | list of str | Non-fatal warnings (e.g. LLM text rejected); empty when all is well |

The classification node should read `state["recon_summary"]`. There is no
human approval step between recon and classification.

## Versioning policy

- `schema_version` follows semver and is a `const` in the schema, so a
  consumer validating against the wrong version fails loudly.
- While the contract is `0.x` (draft), any breaking change (removed, renamed,
  or retyped field, new enum value, new required field) bumps the minor
  version (`0.2.0` to `0.3.0`). Description-only changes bump the patch
  version.
- From `1.0.0`: breaking changes bump the major version; adding an optional
  field bumps the minor version.
- Every change is agreed with Group 2 first, lands in one PR together with the
  updated schema, example output, and this page, and is announced to Group 2.
