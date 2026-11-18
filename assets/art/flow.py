"""Where it fits: the four agents and the human gate.

Run from the repo root:  python assets/art/flow.py
Writes assets/flow.svg.
"""

from __future__ import annotations

from html import escape

from kit import (
    BG,
    DIM,
    FAINT,
    GOLD,
    INK,
    IRIS,
    PINK,
    ROOT,
    SUNSET,
    TEAL,
    TWINKLE_CSS,
    Layer,
    box,
    mix,
    num,
    ramp,
    show_window,
    svg_doc,
)

W = 1280
T = 12
CW, CH = 8.4, 19.0
TOP = 104
ROWS = 6
RAIL = TOP + (ROWS - 1) * CH + 34

css = [TWINKLE_CSS]
_n = 0


def window(a: float, b: float, inner: str, fade: float = 0.012) -> str:
    global _n
    _n += 1
    css.append(show_window(f"w{_n}", a, b, fade))
    return f'<g style="opacity:0;animation:w{_n} {T}s linear infinite">{inner}</g>'


def t(x: float, y: float, s: str, fill: str, size: float = 14, extra: str = "") -> str:
    return f'<text x="{num(x)}" y="{num(y)}" font-size="{size}" fill="{fill}"{extra}>{escape(s, quote=False)}</text>'


# kind, x, cols, index, name, owner, caption
_SPEC = [
    ("src", 17, "", "SCAN FILE", "", "json or nmap xml"),
    ("card", 19, "01", "RECON", "THIS REPO", "summarize the scan"),
    ("card", 19, "02", "CLASSIFY", "GROUP 2", "findings + cvss"),
    ("gate", 0, "", "", "", ""),
    ("card", 19, "03", "PRIORITIZE", "", "rank by risk"),
    ("card", 19, "04", "REPORT", "", "draft for sign-off"),
]
GATE_W = 130.0
_widths = [GATE_W if k == "gate" else c * CW for k, c, *_ in _SPEC]
_gap = (1200 - sum(_widths)) / (len(_SPEC) - 1)
NODES = []
_x = 40.0
for (kind, cols, *rest), w in zip(_SPEC, _widths, strict=False):
    NODES.append((kind, _x, cols, *rest))
    _x += w + _gap
GATE_C = NODES[3][1] + GATE_W / 2
HOLD = [(0.02, 0.08), (0.14, 0.24), (0.30, 0.38), (0.44, 0.66), (0.72, 0.80), (0.86, 0.96)]
COLOR = [DIM, SUNSET[1][1], TEAL, GOLD, ramp(SUNSET, 0.75), ramp(IRIS, 0.95)]


def center(i: int) -> float:
    kind, x, cols, *_ = NODES[i]
    return GATE_C if kind == "gate" else x + (cols // 2) * CW + CW / 2


frames = Layer()
parts: list[str] = []
for i, (kind, x, cols, idx, name, owner, cap) in enumerate(NODES):
    a, b = HOLD[i]
    if kind == "gate":
        dim_d, lit_d = Layer(), Layer()
        n, dy = 4, 11.0
        cy = TOP + 2.5 * CH - 4
        for k in range(-n, n + 1):
            half = (n - abs(k)) * 1.75 * CW + CW * 0.55
            y = cy + k * dy
            left = "/" if k < 0 else ("\\" if k > 0 else "<")
            right = "\\" if k < 0 else ("/" if k > 0 else ">")
            for lay, col in ((dim_d, mix(GOLD, BG, 0.45)), (lit_d, GOLD)):
                lay.add(round(GATE_C - half - CW / 2, 1), y, left, col)
                lay.add(round(GATE_C + half - CW / 2, 1), y, right, col)
        parts.append(f'<g font-size="15" font-weight="700">{dim_d.svg()}</g>')
        parts.append(window(a, b, f'<g font-size="15" font-weight="700">{lit_d.svg()}</g>'))
        label = t(
            GATE_C, cy - 2, "HUMAN", GOLD, 11, ' text-anchor="middle" letter-spacing="2"'
        ) + t(GATE_C, cy + 12, "GATE", GOLD, 11, ' text-anchor="middle" letter-spacing="2"')
        parts.append(label)
        continue

    lit_frame = Layer()
    if i == 1:
        box(frames, x, TOP, cols, ROWS, mix(SUNSET[1][1], BG, 0.25), CW, CH)
    else:
        box(frames, x, TOP, cols, ROWS, FAINT, CW, CH)
        box(lit_frame, x, TOP, cols, ROWS, COLOR[i], CW, CH)
    tx = x + 2 * CW
    if idx:
        parts.append(t(tx, TOP + CH * 1.1, idx, DIM, 12, ' letter-spacing="2"'))
    if owner:
        parts.append(
            t(
                x + (cols - 2) * CW,
                TOP + CH * 1.1,
                owner,
                DIM if i != 1 else SUNSET[1][1],
                10,
                ' text-anchor="end" letter-spacing="1.5"',
            )
        )
    name_y = TOP + CH * (2.6 if idx else 2.2)
    cap_y = TOP + CH * (3.95 if idx else 3.55)
    if i == 1:
        # the highlighted agent: gradient name and a small glyph eye that blinks
        parts.append(
            '<text font-size="18" font-weight="700" letter-spacing="1.5" y="'
            + num(name_y)
            + '">'
            + "".join(
                f'<tspan x="{num(tx + k * 12.3)}" fill="{ramp(SUNSET, k / 5)}">{c}</tspan>'
                for k, c in enumerate(name)
            )
            + "</text>"
        )
        eye = [("<", PINK), ("(", TEAL), ("@", GOLD), (")", TEAL), (">", PINK)]
        ex = x + (cols - 8) * CW
        parts.append(
            '<g class="peek" font-size="14" font-weight="700">'
            + "".join(t(ex + k * 8.4, name_y, c, col) for k, (c, col) in enumerate(eye))
            + "</g>"
        )
    else:
        parts.append(
            t(
                tx,
                name_y,
                name,
                "#6f939a",
                18 if idx else 14,
                ' font-weight="700" letter-spacing="1.5"',
            )
        )
        bright = f'<g font-size="16">{lit_frame.svg()}</g>' + t(
            tx, name_y, name, COLOR[i], 18 if idx else 14, ' font-weight="700" letter-spacing="1.5"'
        )
        done = t(
            tx,
            name_y,
            name,
            mix(COLOR[i], BG, 0.4),
            18 if idx else 14,
            ' font-weight="700" letter-spacing="1.5"',
        )
        parts.append(
            window(b + 0.01, 0.975, done, 0.015) + window(a - 0.01, b + 0.01, bright, 0.015)
        )
    parts.append(t(tx, cap_y, cap, DIM, 13))

# rail, ticks, lit rail
rail, lit = Layer(), Layer()
x = 40.0
while x < 1240:
    rail.add(round(x, 1), RAIL, "─", "#0d252e")
    lit.add(round(x, 1), RAIL, "━", mix(ramp(SUNSET, (x - 40) / 1200), BG, 0.25))
    x += CW
for i, node in enumerate(NODES):
    c = round(center(i), 1)
    if node[0] == "gate":
        rail.add(c, RAIL - 18, "│", mix(GOLD, BG, 0.5))
    else:
        rail.add(c, TOP + (ROWS - 1) * CH + 15, "│", FAINT)
    rail.add(c, RAIL, "┴", FAINT)

kf = []
for i, (a, b) in enumerate(HOLD):
    kf += [(a, center(i)), (b, center(i))]
pts = [(0.0, center(0))] + kf + [(1.0, center(5))]
css.append(
    "@keyframes tok{"
    + "".join(f"{p * 100:.2f}%{{transform:translateX({x:.1f}px)}}" for p, x in pts)
    + "}"
)
css.append(show_window("tokfade", 0.02, 0.96, 0.02))
# The lit line is revealed by a clip rectangle that rides the same CSS animation
# as the token, so its edge always sits under the token (one clock, no drift).
fill_clip = (
    f'<clipPath id="filled"><rect x="-2400" y="{RAIL - 20}" height="30" width="2400" '
    f'style="animation:tok {T}s cubic-bezier(.6,0,.4,1) infinite"/></clipPath>'
)

# what the token carries on each leg
LABELS = ["scan", "recon_summary", "findings + cvss", "approved", "ranked risks", "report draft"]
label_svg = []
for k, lab in enumerate(LABELS):
    a = 0.0 if k == 0 else HOLD[k][1] - 0.015
    b = HOLD[k + 1][1] - 0.015 if k + 1 < len(HOLD) else 0.96
    col = SUNSET[1][1] if lab == "recon_summary" else INK
    label_svg.append(window(a, b, t(0, RAIL + 24, lab, col, 12.5, ' text-anchor="middle"'), 0.006))

token = f"""
<g style="animation:tok {T}s cubic-bezier(.6,0,.4,1) infinite">
  <g style="animation:tokfade {T}s linear infinite">
    <circle cx="0" cy="{RAIL - 5}" r="16" fill="url(#tokglow)"/>
    {t(-27, RAIL + 1, ".", mix(GOLD, BG, 0.75), 16)}
    {t(-19, RAIL + 1, ":", mix(GOLD, BG, 0.5), 16)}
    {t(-5, RAIL + 1, "◆", GOLD, 16)}
    {"".join(label_svg)}
  </g>
</g>"""

css.append("@keyframes wait{0%,49%{opacity:1}50%,100%{opacity:.2}}")
a, b = HOLD[3]
waiting = window(
    a,
    b,
    '<g style="animation:wait .9s steps(1) infinite">'
    + t(
        GATE_C,
        RAIL + 48,
        "awaiting approval",
        GOLD,
        12.5,
        ' text-anchor="middle" letter-spacing="1"',
    )
    + "</g>",
)
css.append(
    ".peek{animation:peek 5s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
    "@keyframes peek{0%,88%,100%{transform:scaleY(1)}93%{transform:scaleY(.1)}}"
)

FOOT = RAIL + 76
H = int(FOOT + 50)
body = f"""
<rect width="{W}" height="{H}" fill="{BG}"/>
<defs>
  <radialGradient id="tokglow">
    <stop offset="0" stop-color="{GOLD}" stop-opacity=".45"/>
    <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
  </radialGradient>
  {fill_clip}
</defs>
<g font-size="12" fill="{DIM}" letter-spacing="2.5">
  <text x="40" y="44">WHERE IT FITS</text>
  <text x="1240" y="44" text-anchor="end">AGENT 1 OF 4 . AI-ASSISTED PENTEST POC</text>
</g>
<line x1="40" y1="60" x2="1240" y2="60" stroke="{FAINT}"/>
<g font-size="16">{frames.svg()}</g>
{"".join(parts)}
<g font-size="16">{rail.svg()}</g>
{window(0.02, 0.96, f'<g font-size="16" clip-path="url(#filled)">{lit.svg()}</g>', 0.02)}
{token}
{waiting}
<line x1="40" y1="{FOOT}" x2="1240" y2="{FOOT}" stroke="{FAINT}"/>
<text x="40" y="{FOOT + 28}" font-size="13" fill="{DIM}">decision support only. never scans, never touches a target, never rates risk.</text>
<text x="1240" y="{FOOT + 28}" font-size="12" fill="{DIM}" text-anchor="end" letter-spacing="2.5">SYNTHETIC DATA ONLY</text>
"""

svg = svg_doc(
    W,
    H,
    "Where the recon agent fits",
    "A scan file goes to recon, then classification, then a human approval gate, then risk prioritization and a "
    "report draft. A token carrying recon_summary moves along the line and waits at the gate.",
    body,
    "\n".join(css),
)
out = ROOT / "assets" / "flow.svg"
out.write_text(svg, encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} ({len(svg) // 1024} KB, height {H})")
