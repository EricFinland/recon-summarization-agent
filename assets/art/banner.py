"""Top banner: ASCII sea turtles drifting past, next to the project name.

Run from the repo root:  python assets/art/banner.py
Writes assets/banner.svg.

The turtles come from turtle_swim.json.gz: glyph frames of one full flipper
stroke, recorded from an ASCII creature engine at two headings (swimming right
and swimming left), with the engine's own palette. They are drawn the way the
engine draws them: upright glyphs on an 8 px grid, a faint colour tile behind
every interior glyph, and a soft bloom baked from the same frames. Each turtle
surges forward on the power stroke. Everything is CSS animation, no scripts.
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
    SUNSET,
    Layer,
    box_blur,
    hex2rgb,
    mix,
    num,
    pixel_blocks,
    png_data_uri,
    stars,
    svg_doc,
)

W, H = 1280, 520
PANEL = (0, 59, 744, 415)  # x, y, w, h of the water on the left
rnd = random.Random(11)

# ----------------------------------------------------------------- turtle frames

swim = json.loads(gzip.decompress((ROOT / "assets/art/turtle_swim.json.gz").read_bytes()))
GC = swim["C"]  # 8 px cells, as in the engine
CELL_FONT, GLYPH_FONT = GC + 3, GC + 2  # the engine's glyph sizes
NF = len(swim["right"]["frames"])


def css_hex(c: str) -> str:
    r, g, b = (int(v) for v in c[c.index("(") + 1 : c.index(")")].split(","))
    return f"#{r:02x}{g:02x}{b:02x}"


PALS = {swim["pal"][k]: [css_hex(c) for c in v] for k, v in swim["css"].items()}


def frame_svg(records: list) -> str:
    tiles: dict[str, list[str]] = defaultdict(list)
    runs: dict[tuple[str, float, int], list[tuple[float, float, str]]] = defaultdict(list)
    for gx, gy, ch, p, lvl, a, kind in records:
        pal = PALS[p]
        if kind == "c":  # interior glyphs sit on a faint tile of their colour
            tiles[pal[max(1, lvl - 1)]].append(f"M{num(gx * GC)} {num(gy * GC)}h{GC}v{GC}h-{GC}z")
        size = GLYPH_FONT if kind == "g" else CELL_FONT
        x = (gx + 0.5) * GC
        y = (gy + 0.5) * GC + size * 0.36
        runs[(pal[lvl], round(min(1.0, a), 1), size)].append((x, y, ch))
    out = ['<g opacity=".2">']
    out += [f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in sorted(tiles.items())]
    out.append("</g>")
    for (color, a, size), gl in sorted(runs.items()):
        gl.sort(key=lambda g: (g[1], g[0]))
        xs = " ".join(num(round(x, 1)) for x, _, _ in gl)
        ys = " ".join(num(round(y, 1)) for _, y, _ in gl)
        chars = "".join(escape(c, quote=False) for _, _, c in gl)
        op = "" if a >= 1 else f' fill-opacity="{a:g}"'
        out.append(f'<text x="{xs}" y="{ys}" fill="{color}" font-size="{size}"{op}>{chars}</text>')
    return "".join(out)


def bloom(frames: list) -> tuple[str, float, float, float, float]:
    """The engine's bloom, baked: the drawn layer averaged over the stroke, blurred three ways."""
    sub = 2  # image pixels per cell
    pad = 7  # cells of room for the glow
    xs = [r[0] for f in frames for r in f]
    ys = [r[1] for f in frames for r in f]
    x0, y0 = min(xs) - pad, min(ys) - pad
    w, h = (max(xs) - x0 + pad + 1) * sub, (max(ys) - y0 + pad + 1) * sub
    acc = [[[0.0, 0.0, 0.0] for _ in range(w)] for _ in range(h)]
    for f in frames:
        for gx, gy, _ch, p, lvl, a, kind in f:
            pal = PALS[p]
            glyph = [c * 0.32 * a for c in hex2rgb(pal[lvl])]
            tile = [c * 0.2 for c in hex2rgb(pal[max(1, lvl - 1)])] if kind == "c" else [0, 0, 0]
            for sy in range(sub):
                for sx in range(sub):
                    px = acc[(gy - y0) * sub + sy][(gx - x0) * sub + sx]
                    for i in range(3):
                        px[i] += (glyph[i] + tile[i]) / len(frames)
    chans = [[[px[i] for px in row] for row in acc] for i in range(3)]
    out = [[[0.0, 0.0, 0.0] for _ in range(w)] for _ in range(h)]
    for radius, weight in ((1, 0.3), (3, 0.45), (6, 0.55)):
        for i in range(3):
            bl = box_blur(chans[i], radius)
            for yy in range(h):
                for xx in range(w):
                    out[yy][xx][i] += bl[yy][xx] * weight
    pixels = []
    for row in out:
        prow = []
        for r, g, b in row:
            # glow strength becomes alpha and the hue stays the colour, so it blends on any background
            lum = max(r, g, b) * 2.3
            s = 2.3 / lum if lum > 0 else 0.0
            rgb = (
                min(255, int(r * s * 255)),
                min(255, int(g * s * 255)),
                min(255, int(b * s * 255)),
            )
            prow.append((*rgb, int(min(1.0, lum) * 255)))
        pixels.append(prow)
    return png_data_uri(pixels), x0 * GC, y0 * GC, w * GC / sub, h * GC / sub


sets = {}
for side in ("right", "left"):
    frames = swim[side]["frames"]
    uri, bx, by, bw, bh = bloom(frames)
    defs = [
        f'<image id="glow-{side}" href="{uri}" x="{num(bx)}" y="{num(by)}" width="{num(bw)}" height="{num(bh)}"/>'
    ]
    defs += [f'<g id="{side}{k}">{frame_svg(fr)}</g>' for k, fr in enumerate(frames)]
    sets[side] = {"ang": swim[side]["ang"], "defs": "".join(defs)}

# ----------------------------------------------------------------- the turtles

css: list[str] = [
    f"@keyframes fl{{0%{{visibility:visible}}{100 / NF:.3f}%,100%{{visibility:hidden}}}}"
]


def surge(row: float) -> float:
    """Forward speed over one stroke: a push on the power stroke, a glide after."""
    return 0.35 + 0.65 * max(0.0, math.sin(row)) ** 1.5


# (heading set, start x, start y, stroke period s, strokes per crossing, opacity, phase 0..1)
TURTLES = [
    ("right", -110, 400, 3.6, 7, 1.0, 0.30),
    ("left", 860, 250, 4.0, 6, 1.0, 0.05),
    ("right", -110, 238, 4.4, 6, 0.9, 0.78),
    ("left", 860, 430, 4.8, 5, 0.8, 0.55),
]

turtle_svg = []
for i, (side, x0, y0, period, strokes, op, phase) in enumerate(TURTLES):
    T = period * strokes
    ang = sets[side]["ang"]
    dist = 980
    dx, dy = math.cos(ang) * dist, math.sin(ang) * dist
    n = 200
    acc = [0.0]
    for k in range(n):
        acc.append(acc[-1] + surge(2 * math.pi * strokes * (k + 0.5) / n))
    keys = "".join(
        f"{k / n * 100:.2f}%{{transform:translate({x0 + dx * acc[k] / acc[-1]:.1f}px,"
        f"{y0 + dy * acc[k] / acc[-1]:.1f}px)}}"
        for k in range(n + 1)
    )
    css.append(f"@keyframes sw{i}{{{keys}}}")
    delay = -phase * T
    css.append(f".sw{i}{{animation:sw{i} {T:.2f}s linear {delay:.2f}s infinite}}")
    css.append(f".f{i}{{visibility:hidden;animation:fl {period:.2f}s step-end infinite}}")
    uses = [f'<use href="#glow-{side}"/>']
    for k in range(NF):
        d = -((NF - k) % NF) * period / NF + delay
        uses.append(f'<use href="#{side}{k}" class="f{i}" style="animation-delay:{d:.3f}s"/>')
    turtle_svg.append(f'<g class="sw{i}" opacity="{op}">{"".join(uses)}</g>')

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
  <linearGradient id="edges" x1="0" x2="1">
    <stop offset="0" stop-color="#000"/>
    <stop offset=".07" stop-color="#fff"/>
    <stop offset=".9" stop-color="#fff"/>
    <stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="water" maskUnits="userSpaceOnUse" x="{px}" y="{py}" width="{pw}" height="{ph}">
    <rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="url(#edges)"/>
  </mask>
  {sets["right"]["defs"]}
  {sets["left"]["defs"]}
</defs>
<rect x="0" y="{py}" width="{W}" height="{ph}" fill="url(#depth)"/>
<g font-size="10">{drift.svg()}</g>
<g mask="url(#water)">
  {rays}
  <g>{"".join(bubbles)}</g>
  <g font-weight="700" text-anchor="middle">{"".join(turtle_svg)}</g>
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
