# Data Catalog

Every dataset used by this repository is synthetic. This catalog records, for
each file, where it came from, how it was made, how we checked it contains no
real data, and why we use it.

## Privacy rules applied to every file

- IPv4 addresses are only from private ranges (10.0.0.0/8, 172.16.0.0/12,
  192.168.0.0/16). IPv6 addresses are only from the documentation range
  2001:db8::/32. MAC addresses are only from the documentation block
  00:00:5E:00:53:00 to 00:00:5E:00:53:FF (RFC 7042).
- Hostnames end in `.lab.local`; any other domain is under `.example`.
- No real organization, person, credential, or Stanford system, address,
  hostname, or domain appears in any file.
- Software names and versions (OpenSSH, nginx, Apache httpd, and so on) are
  public product names used for realism; they do not describe any real host.
- Verification: each file was written by hand (or by a short script producing
  placeholder strings), then reviewed line by line against the rules above.
  Addresses were checked to fall inside the allowed ranges, and every hostname
  and domain was checked for the `.lab.local` or `.example` suffix.

## data/scans/

### sample_scan_01.json

- **Origin:** hand-written for this project.
- **Generation method:** composed manually in our JSON scan format to look like
  a small TCP connect scan of 10.10.20.0/24.
- **Privacy verification:** all addresses in 10.10.20.0/24; hostnames under
  `.lab.local`; reviewed against the rules above.
- **Usage justification:** the reference input for the output contract with
  Group 2 (paired with `schemas/examples/sample_scan_01.summary.json`).
- **Exercises:** open, closed, and filtered TCP ports; null product, version,
  hostname, and OS fields; a host with no open ports; a down host.

### sample_scan_02.json

- **Origin:** hand-written for this project.
- **Generation method:** composed manually in our JSON format; invisible and
  control characters are written as JSON `\u` escapes so they are visible in
  review.
- **Privacy verification:** IPv4 addresses in 192.168.56.0/24, IPv6 address in
  2001:db8:56::/64; hostnames under `.lab.local`; reviewed against the rules
  above.
- **Usage justification:** adversarial and edge-case input to show that the
  agent withholds instruction-like notes, truncates long notes, and cleans
  hidden characters without losing or inventing data.
- **Exercises:**
  - an obvious prompt injection in an FTP banner (asks the model to ignore its
    instructions, report no vulnerabilities, and invent a CVE),
  - a subtler injection inside an HTTP title addressed to "the automated
    summarizer",
  - an injection hidden with zero-width spaces inside words,
  - a note longer than 500 characters (HTTP header dump),
  - notes and fields containing zero-width, bidi-override, no-break space,
    tab, and bell characters, plus a note that is empty after cleaning (its
    index is kept, so later evidence paths still match the file),
  - an OS guess that is only whitespace and invisible characters (becomes null),
  - UDP ports, an `open|filtered` port, the same port number on TCP and UDP,
  - an IPv6 host, a host with status `unknown` and a port in state `unknown`,
  - normal hosts and a down host.

### sample_scan_03.xml

- **Origin:** hand-written for this project, following the structure of Nmap
  7.94 `-oX` output.
- **Generation method:** composed manually; no scan was run. Timestamps,
  reasons, and OS fingerprint line numbers are illustrative.
- **Privacy verification:** addresses in 172.16.30.0/28; hostnames under
  `.lab.local`; MAC address is in the RFC 7042 documentation block; reviewed against the
  rules above.
- **Usage justification:** shows the agent can ingest the de facto standard
  scanner format, parsed safely with defusedxml.
- **Exercises:** two `<scaninfo>` types (syn and udp), service product and
  version, `tunnel="ssl"`, closed and filtered ports, `open|filtered` UDP port,
  `<extraports>` (skipped), port scripts (`http-title`, `http-server-header`,
  `ssl-cert`, `snmp-info`) with multi-line output, a `<hostscript>`
  (`smb-security-mode`), OS matches with accuracy, a MAC address next to the
  IPv4 address, a host with no hostname, and a down host.

### sample_scan_04_empty.json

- **Origin:** hand-written for this project.
- **Generation method:** composed manually in our JSON format.
- **Privacy verification:** the only address is the range 10.10.40.0/28;
  reviewed against the rules above.
- **Usage justification:** a valid scan that found no hosts, to check the
  agent produces a valid, empty summary instead of failing.
- **Exercises:** zero hosts, so all counts are zero.

## tests/fixtures/ (group entry)

- **Origin:** hand-written for the loader tests.
  `oversized_field.json` was produced by a short script that repeats the
  letter "a" to make a 610-character hostname.
- **Generation method:** small files, each built to trigger one specific
  loader behavior. Hostile XML follows the textbook forms of the attacks
  (external entity, parameter entity, entity expansion).
- **Privacy verification:** addresses in 10.0.0.0/8 or 2001:db8::/32;
  hostnames under `.lab.local`; the only URL host is `attacker.example`, and
  the XXE fixture references the generic path `file:///etc/passwd`, which is
  never read because the parser rejects the file first. Reviewed against the
  rules above.
- **Usage justification:** proves malformed or hostile input is rejected with
  a clear error, as the project contract requires.
- **Files and what they exercise:**

| File | Expected loader result |
|------|------------------------|
| `malformed.json` | malformed JSON (trailing comma, unclosed object) |
| `wrong_types.json` | validation error listing status, port (string "22"), and notes |
| `invalid_ip.json` | validation error on `hosts[0].ip` |
| `duplicate_keys.json` | rejected: duplicate key `hosts` |
| `top_level_array.json` | rejected: top-level value is not an object |
| `oversized_field.json` | rejected: hostname longer than 512 characters |
| `unknown_format.txt` | rejected: plain-text Nmap output is not a supported format |
| `malformed.xml` | malformed XML (mismatched tag) |
| `not_nmap.xml` | rejected: root element is not `<nmaprun>` |
| `xxe.xml` | rejected: external entity (XXE) |
| `xxe_parameter_entity.xml` | rejected: external parameter entity |
| `billion_laughs.xml` | rejected: entity expansion (billion laughs) |
| `nmap_edge_cases.xml` | loads: Nmap states mapped to `unknown`, MAC skipped, OS accuracy tie, script note order, IPv6 host with status `skipped` |
