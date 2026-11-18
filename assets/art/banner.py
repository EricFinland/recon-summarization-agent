"""Top banner: ASCII sea turtles drifting past, next to the project name.

Run from the repo root:  python assets/art/banner.py
Writes assets/banner.svg.

The turtle comes from turtle_swim.json.gz: glyph frames of one full flipper
stroke, recorded from an ASCII creature engine. Each turtle on the banner reuses
those frames (SVG <use>), at its own size, depth, speed and heading, and surges
forward on the power stroke. Everything is CSS animation with no scripts.
"""

from __future__ import annotations

import gzip
import json
import math
import random
from collections import defaultdict
from html import escape

from kit import (
    BG,
    DIM,
    FAINT,
    INK,
    ROOT,
    SEA,
    SUNSET,
    Layer,
    mix,
    num,
    pixel_blocks,
    ramp,
    stars,
    svg_doc,
)

W, H = 1280, 520
PANEL = (0, 59, 744, 415)  # x, y, w, h of the water on the left
SKIN = [(0.0, "#0b1b1e"), (0.45, "#5f8276"), (1.0, "#f3e7c6")]
rnd = random.Random(11)

# ----------------------------------------------------------------- turtle frames

swim = json.loads(gzip.decompress((ROOT / "assets/art/turtle_swim.json.gz").read_bytes()))
GC = swim["C"]
FRAMES = swim["frames"]
NF = len(FRAMES)
GLYPH_SIZE = 6.7
PAL = swim["pal"]


def glyph_color(p: int, lvl: int, a: float) -> str:
    if p == PAL["shell"]:
        c = ramp(SEA, 0.18 + 0.82 * lvl / 6)
    elif p == PAL["eye"]:
        c = "#f0fffa" if lvl >= 5 else "#04121a"
    else:
        c = ramp(SKIN, 0.12 + 0.88 * lvl / 6)
    return mix(BG, c, max(0.0, min(1.0, a)))


def frame_svg(records: list) -> str:
    runs: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for gx, gy, ch, p, lvl, a, _kind in records:
        x = (gx + 0.5) * GC
        y = (gy + 0.5) * GC + GLYPH_SIZE * 0.36
        runs[glyph_color(p, lvl, a)].append((x, y, ch))
    out = []
    for color, gl in sorted(runs.items()):
        gl.sort(key=lambda g: (g[1], g[0]))
        xs = " ".join(num(round(x, 1)) for x, _, _ in gl)
        ys = " ".join(num(round(y, 1)) for _, y, _ in gl)
        chars = "".join(escape(c, quote=False) for _, _, c in gl)
        out.append(f'<text x="{xs}" y="{ys}" fill="{color}">{chars}</text>')
    return "".join(out)


frame_defs = "".join(f'<g id="t{k}">{frame_svg(fr)}</g>' for k, fr in enumerate(FRAMES))

# ----------------------------------------------------------------- the turtles

css: list[str] = [
    f"@keyframes fl{{0%{{visibility:visible}}{100 / NF:.3f}%,100%{{visibility:hidden}}}}"
]


def surge(row: float) -> float:
    """Forward speed over one stroke: a push on the power stroke, a glide after."""
    return 0.35 + 0.65 * max(0.0, math.sin(row)) ** 1.5


# (scale, opacity, stroke period s, strokes per crossing, start, end, wobble px, phase 0..1)
TURTLES = [
    (0.52, 0.42, 4.8, 6, (-90, 352), (840, 300), 18, 0.55),
    (0.68, 0.62, 4.2, 5, (840, 150), (-110, 214), 24, 0.15),
    (1.00, 1.00, 3.6, 7, (-150, 268), (900, 196), 30, 0.38),
    (0.44, 0.36, 5.2, 5, (820, 392), (-90, 360), 12, 0.8),
]

turtle_svg = []
for i, (sc, op, period, strokes, (x0, y0), (x1, y1), wob, phase) in enumerate(TURTLES):
    T = period * strokes
    # distance covered follows the stroke, so the turtle surges as its flippers push
    n = 240
    acc = [0.0]
    for k in range(n):
        acc.append(acc[-1] + surge(2 * math.pi * strokes * (k + 0.5) / n))
    keys = []
    for k in range(n + 1):
        f = acc[k] / acc[-1]
        x = x0 + (x1 - x0) * f
        y = y0 + (y1 - y0) * f + wob * math.sin(2 * math.pi * (k / n) * 1.5 + i)
        keys.append((k / n, x, y))
    frames = []
    for k, (p, x, y) in enumerate(keys):
        q = keys[min(k + 1, n)]
        r = keys[max(k - 1, 0)]
        ang = math.degrees(math.atan2(q[2] - r[2], q[1] - r[1]))
        frames.append(
            f"{p * 100:.2f}%{{transform:translate({x:.1f}px,{y:.1f}px) rotate({ang:.1f}deg)}}"
        )
    css.append(f"@keyframes sw{i}{{{''.join(frames)}}}")
    delay = -phase * T
    css.append(f".sw{i}{{animation:sw{i} {T:.2f}s linear {delay:.2f}s infinite}}")
    css.append(f".f{i}{{visibility:hidden;animation:fl {period:.2f}s step-end infinite}}")
    uses = []
    for k in range(NF):
        d = -((NF - k) % NF) * period / NF + delay
        uses.append(f'<use href="#t{k}" class="f{i}" style="animation-delay:{d:.3f}s"/>')
    turtle_svg.append(
        f'<g class="sw{i}" opacity="{op}"><g transform="scale({sc})">'
        f'<ellipse cx="0" cy="0" rx="78" ry="64" fill="url(#shell-glow)"/>{"".join(uses)}</g></g>'
    )

# ----------------------------------------------------------------- the water

bubbles = []
for b in range(18):
    x = rnd.uniform(30, 710)
    dur = rnd.uniform(7, 13)
    delay = -rnd.uniform(0, dur)
    size = rnd.choice([9, 10, 11, 13])
    ch = rnd.choice(["o", "o", ".", "°", "0"])
    sway = rnd.uniform(4, 10)
    css.append(
        f"@keyframes bs{b}{{0%,100%{{transform:translateX(0)}}50%{{transform:translateX({sway:.1f}px)}}}}"
    )
    bubbles.append(
        f'<g style="animation:rise {dur:.2f}s linear {delay:.2f}s infinite">'
        f'<text x="{x:.1f}" y="470" font-size="{size}" fill="#9ee8d4" '
        f'style="animation:bs{b} {dur / 3:.2f}s ease-in-out infinite">{escape(ch)}</text></g>'
    )
css.append(
    "@keyframes rise{0%{transform:translateY(0);opacity:0}12%{opacity:.55}80%{opacity:.35}"
    "100%{transform:translateY(-420px);opacity:0}}"
)

rays = "".join(
    f'<polygon points="{x:.0f},59 {x + w:.0f},59 {x + w - 170:.0f},474 {x - 230:.0f},474" '
    f'fill="url(#ray)" opacity="{o}"/>'
    for x, w, o in [(150, 60, 0.5), (330, 90, 0.7), (520, 50, 0.45), (640, 70, 0.35)]
)

drift = Layer()
stars(drift, W, H, 240, seed=9, avoid=lambda x, y: 744 < x < 1250 and 80 < y < 470)
drift.items = [(x, y, c, mix(BG, "#3fc6b0", 0.35), cls) for x, y, c, _, cls in drift.items]

# ----------------------------------------------------------------- right side

TX = 768
title_svg = pixel_blocks("RECON", TX, 150, 15, SUNSET, shadow="#0b2a33")
HOSTS = [
    ("10.10.20.5", "up", "ssh http https"),
    ("10.10.20.12", "up", "mysql"),
    ("10.10.20.30", "up", "microsoft-ds ms-wbt-server"),
    ("10.10.20.44", "up", "no open ports"),
    ("10.10.20.99", "down", ""),
]
readout = [
    f'<text x="{TX}" y="346" font-size="12" fill="{DIM}" letter-spacing="1.5">SUMMARY.HOSTS[]</text>'
]
for i, (ip, status, svc) in enumerate(HOSTS):
    y = 372 + i * 19
    col = INK if status == "up" else "#ff6f61"
    readout.append(
        f'<g font-size="13"><text x="{TX}" y="{y}" fill="{col}">{ip}</text>'
        f'<text x="{TX + 118}" y="{y}" fill="{DIM}">{status}</text>'
        f'<text x="{TX + 168}" y="{y}" fill="#9ee8d4">{escape(svc)}</text></g>'
    )

css.append(
    ".tw1{animation:tw 4.1s ease-in-out infinite}"
    ".tw2{animation:tw 5.3s ease-in-out -1.7s infinite}"
    ".tw3{animation:tw 6.7s ease-in-out -3.2s infinite}"
    "@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}"
    ".f0,.f1,.f2,.f3{visibility:hidden}}"
)

px, py, pw, ph = PANEL
body = f"""
<rect width="{W}" height="{H}" fill="{BG}"/>
<defs>
  <linearGradient id="depth" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0a3a48" stop-opacity=".55"/>
    <stop offset=".6" stop-color="#062634" stop-opacity=".25"/>
    <stop offset="1" stop-color="{BG}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="ray" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#9ee8d4" stop-opacity=".09"/>
    <stop offset="1" stop-color="#9ee8d4" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="shell-glow">
    <stop offset="0" stop-color="#3fc6b0" stop-opacity=".16"/>
    <stop offset="1" stop-color="#3fc6b0" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="edges" x1="0" x2="1">
    <stop offset="0" stop-color="#000"/>
    <stop offset=".07" stop-color="#fff"/>
    <stop offset=".9" stop-color="#fff"/>
    <stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="water" maskUnits="userSpaceOnUse" x="{px}" y="{py}" width="{pw}" height="{ph}">
    <rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="url(#edges)"/>
  </mask>
  {frame_defs}
</defs>
<rect x="0" y="{py}" width="{W}" height="{ph}" fill="url(#depth)"/>
<g font-size="10">{drift.svg()}</g>
<g mask="url(#water)">
  {rays}
  <g>{"".join(bubbles)}</g>
  <g font-size="{GLYPH_SIZE}" font-weight="700" text-anchor="middle">{"".join(turtle_svg)}</g>
</g>

<g font-size="12" fill="{DIM}" letter-spacing="2">
  <text x="40" y="44">01 / 04</text>
  <text x="{W - 40}" y="44" text-anchor="end">SCAN IN . SUMMARY OUT</text>
</g>
<line x1="40" y1="58" x2="{W - 40}" y2="58" stroke="{FAINT}" stroke-width="1"/>

<rect x="{TX}" y="102" width="214" height="28" fill="{INK}"/>
<text x="{TX + 12}" y="121" font-size="13" fill="{BG}" letter-spacing="1.5">AGENT 01 . PENTEST POC</text>
{title_svg}
<text x="{TX}" y="300" font-size="25" fill="{INK}" letter-spacing="5">summarization agent</text>
{"".join(readout)}

<line x1="40" y1="{H - 46}" x2="{W - 40}" y2="{H - 46}" stroke="{FAINT}" stroke-width="1"/>
<g font-size="12" fill="{DIM}" letter-spacing="1.5">
  <text x="40" y="{H - 22}">reads every host. invents nothing.</text>
  <text x="{W - 40}" y="{H - 22}" text-anchor="end">python . langgraph . synthetic data only</text>
</g>
"""

svg = svg_doc(
    W,
    H,
    "Recon Summarization Agent",
    "A few ASCII sea turtles drift through dark water next to the project name and a sample "
    "summary of five scanned hosts.",
    body,
    "".join(css),
)
out = ROOT / "assets" / "banner.svg"
out.write_text(svg, encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} ({len(svg) // 1024} KB)")
