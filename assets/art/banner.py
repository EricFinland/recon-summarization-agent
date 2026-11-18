"""Top banner: an ASCII spider walking a web of scanned hosts.

Run from the repo root:  python assets/art/banner.py
Writes assets/banner.svg.

The web's nodes are the hosts in data/scans/sample_scan_01.json. The spider
walks the strands from host to host and stops to read each one, and the
summary on the right gains a line per host as it goes.

The spider itself comes from spider_gait.json.gz: glyph frames of one leg cycle
(walking) and a slow idle loop, recorded from an ASCII creature engine. Every
other part of the picture is computed here. Everything runs on CSS animations
that share one loop, so the parts never drift apart.
"""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from html import escape

from kit import (
    BG,
    DIM,
    FAINT,
    INK,
    ROOT,
    WARM,
    Layer,
    mix,
    num,
    pixel_blocks,
    ramp,
    stars,
    svg_doc,
)

W, H = 1280, 520
GOLD_RAMP = [(0.0, "#8f4312"), (0.45, "#ffc562"), (1.0, "#fff4de")]

# ----------------------------------------------------------------- the web

CX, CY, SX = 380, 262, 2.0
RINGS = [24, 50, 76, 102, 128]
SPOKES = 12
SPEED = 95  # px/s along the strands
PAUSE = 1.15  # s spent reading each host
STEP = 1 / 15  # keyframe spacing for the walk, in seconds

# hosts from sample_scan_01, in the order the spider visits them
HOSTS = [
    ((210, 3), "10.10.20.5", "up", "ssh http https"),
    ((300, 3), "10.10.20.12", "up", "mysql"),
    ((0, 3), "10.10.20.30", "up", "microsoft-ds ms-wbt-server"),
    ((90, 3), "10.10.20.44", "up", "no open ports"),
    ((150, 2), "10.10.20.99", "down", ""),
]


def spoke_pt(deg: float, r: float) -> tuple[float, float]:
    a = math.radians(deg)
    return CX + SX * r * math.cos(a), CY + r * math.sin(a)


def ring_pt(deg: float, r: float) -> tuple[float, float]:
    """A point on a ring, where rings are straight chords between spokes."""
    step = 360 / SPOKES
    k = math.floor(deg / step)
    f = deg / step - k
    a, b = spoke_pt(k * step, r), spoke_pt((k + 1) * step, r)
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def leg_points(a1: float, i1: int, a2: float, i2: int) -> list[tuple[float, float]]:
    """Walk along strands: out or in along the spoke, then around the ring."""
    r1, r2 = RINGS[i1], RINGS[i2]
    pts = [spoke_pt(a1, r1 + (r2 - r1) * k / 30) for k in range(31)]
    d = ((a2 - a1) % 360 + 540) % 360 - 180
    n = max(2, math.ceil(abs(d) / 1.5))
    pts += [ring_pt((a1 + d * k / n) % 360, r2) for k in range(1, n + 1)]
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 0.01:
            out.append(p)
    return out


legs = []
for i, ((a1, i1), *_rest) in enumerate(HOSTS):
    (a2, i2), *_ = HOSTS[(i + 1) % len(HOSTS)]
    pts = leg_points(a1, i1, a2, i2)
    cum = [0.0]
    for p, q in zip(pts, pts[1:], strict=False):
        cum.append(cum[-1] + math.dist(p, q))
    legs.append({"pts": pts, "cum": cum, "len": cum[-1], "walk": cum[-1] / SPEED * 1.35})

T = sum(PAUSE + lg["walk"] for lg in legs)
T = round(T / STEP) * STEP
scale_t = T / sum(PAUSE + lg["walk"] for lg in legs)
t0 = 0.0
for lg in legs:
    lg["pause"] = PAUSE * scale_t
    lg["walk"] *= scale_t
    lg["t0"] = t0
    t0 += lg["pause"] + lg["walk"]


def pos_at(tau: float) -> tuple[tuple[float, float], bool]:
    tau %= T
    for lg in legs:
        if tau < lg["t0"] + lg["pause"] + lg["walk"]:
            u = tau - lg["t0"]
            if u < lg["pause"]:
                return lg["pts"][0], False
            f = (u - lg["pause"]) / lg["walk"]
            target = (0.5 - 0.5 * math.cos(math.pi * f)) * lg["len"]
            j = 1
            while j < len(lg["cum"]) - 1 and lg["cum"][j] < target:
                j += 1
            a, b = lg["pts"][j - 1], lg["pts"][j]
            la, lb = lg["cum"][j - 1], lg["cum"][j]
            w = (target - la) / (lb - la) if lb > la else 0
            return (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w), True
    return legs[0]["pts"][0], False


# heading: follows the direction of travel, smoothed; two passes so the loop closes
n_frames = round(T / STEP)
fine = 8
heading = 0.0
track = []
for _pass in range(2):
    track = []
    for k in range(n_frames * fine):
        t = k * STEP / fine
        (ax, ay), _ = pos_at(t)
        (bx, by), _ = pos_at(t + STEP / fine)
        if math.hypot(bx - ax, by - ay) > 0.05:
            want = math.atan2(by - ay, bx - ax)
            d = (want - heading + math.pi) % (2 * math.pi) - math.pi
            heading += d * min(1.0, STEP / fine * 7)
        track.append((t, ax, ay, heading))

# ----------------------------------------------------------------- spider frames

gait = json.loads(gzip.decompress((ROOT / "assets/art/spider_gait.json.gz").read_bytes()))
GC = gait["C"]
GLYPH_SIZE = 6.7
accent = {gait["pal"]["crim"], gait["pal"]["vio"]}


def glyph_color(p: int, lvl: int, a: float) -> str:
    if p in accent:
        c = ramp(GOLD_RAMP, lvl / 6)
    else:
        c = ramp(WARM, 0.22 + 0.78 * lvl / 6)
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


def flipbook(frames: list, period: float, name: str) -> tuple[str, str]:
    n = len(frames)
    css = (
        f"@keyframes {name}{{0%{{visibility:visible}}{100 / n:.3f}%,100%{{visibility:hidden}}}}"
        f".{name}{{visibility:hidden;animation:{name} {period:.3f}s step-end infinite}}"
    )
    parts = []
    for k, fr in enumerate(frames):
        delay = -((n - k) % n) * period / n
        parts.append(f'<g class="{name}" style="animation-delay:{delay:.3f}s">{frame_svg(fr)}</g>')
    return "".join(parts), css


walk_svg, walk_css = flipbook(gait["walk"], 0.62, "gw")
idle_svg, idle_css = flipbook(gait["idle"], gait["idleT"], "gi")

# ----------------------------------------------------------------- timing helpers

css: list[str] = [walk_css, idle_css]
_n = 0


def windows(spans: list[tuple[float, float]], prop: str = "visibility") -> str:
    """Keyframes (fractions of T) where an element is shown; returns a class name."""
    global _n
    _n += 1
    on, off = ("visible", "hidden") if prop == "visibility" else ("1", "0")
    pts = {0.0: off}
    for a, b in spans:
        pts[max(0.0, a)] = on
        if b < 1:
            pts[b] = off
    if spans and spans[0][0] <= 0:
        pts[0.0] = on
    frames = "".join(f"{p * 100:.3f}%{{{prop}:{v}}}" for p, v in sorted(pts.items()))
    name = f"k{_n}"
    css.append(
        f"@keyframes {name}{{{frames}}}.{name}{{{prop}:{off};animation:{name} {T:.3f}s step-end infinite}}"
    )
    return name


walk_spans = [
    ((lg["t0"] + lg["pause"]) / T, (lg["t0"] + lg["pause"] + lg["walk"]) / T) for lg in legs
]
idle_spans = [(lg["t0"] / T, (lg["t0"] + lg["pause"]) / T) for lg in legs]
walk_cls, idle_cls = windows(walk_spans), windows(idle_spans)

moves = "".join(
    f"{t / T * 100:.3f}%{{transform:translate({x:.1f}px,{y:.1f}px) rotate({math.degrees(h):.1f}deg)}}"
    for t, x, y, h in track[::fine]
)
t_end, x_end, y_end, h_end = track[0]
moves += f"100%{{transform:translate({x_end:.1f}px,{y_end:.1f}px) rotate({math.degrees(heading):.1f}deg)}}"
css.append(f"@keyframes crawl{{{moves}}}.crawl{{animation:crawl {T:.3f}s linear infinite}}")

# ----------------------------------------------------------------- web glyphs


def slope_char(dx: float, dy: float) -> str:
    a = math.degrees(math.atan2(dy, dx)) % 180
    if a < 22 or a >= 158:
        return "-"
    if a < 68:
        return "\\"
    if a < 112:
        return "|"
    return "/"


def strand(
    layer: Layer, p: tuple[float, float], q: tuple[float, float], color: str, step: float = 7.0
) -> None:
    n = max(1, round(math.dist(p, q) / step))
    ch = slope_char(q[0] - p[0], q[1] - p[1])
    for k in range(n + 1):
        f = k / n
        layer.add(
            round(p[0] + (q[0] - p[0]) * f, 1), round(p[1] + (q[1] - p[1]) * f + 3, 1), ch, color
        )


web = Layer()
outer = RINGS[-1]
for s in range(SPOKES):
    deg = s * 360 / SPOKES
    strand(web, spoke_pt(deg, 6), spoke_pt(deg, outer + 14), "#4a3420")
for i, r in enumerate(RINGS):
    col = mix("#2e2216", "#5a3d22", i / (len(RINGS) - 1))
    for s in range(SPOKES):
        strand(web, spoke_pt(s * 30, r), spoke_pt((s + 1) * 30, r), col)
# anchor threads out to the edges of the panel
for p, q in [
    (spoke_pt(210, outer + 14), (48, 82)),
    (spoke_pt(330, outer + 14), (712, 82)),
    (spoke_pt(150, outer + 14), (48, 456)),
    (spoke_pt(30, outer + 14), (712, 456)),
]:
    strand(web, p, q, "#3a2a1a", 8)

# strands the spider has walked stay lit until the loop restarts
walked = []
for lg in legs:
    lit = Layer()
    pts = lg["pts"]
    for p, q in zip(pts[::6], pts[6::6], strict=False):
        strand(lit, p, q, "#b8601d")
    strand(lit, pts[-7 if len(pts) > 7 else 0], pts[-1], "#b8601d")
    cls = windows([((lg["t0"] + lg["pause"] + lg["walk"]) / T, 0.995)])
    walked.append(f'<g class="{cls}">{lit.svg()}</g>')

# host nodes and their small address labels
nodes = []
for i, ((deg, ring), ip, status, _svc) in enumerate(HOSTS):
    x, y = spoke_pt(deg, RINGS[ring])
    lg = legs[i]
    seen = windows([(lg["t0"] / T, 0.995)])
    dx, dy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    lx, ly = x + dx * 26, y + dy * 18 + 4
    anchor = "start" if dx > 0.3 else "end" if dx < -0.3 else "middle"
    lit_col = "#ffd486" if status == "up" else "#a4553a"
    nodes.append(
        f'<text x="{num(round(x, 1))}" y="{num(round(y + 4, 1))}" font-size="12" fill="#6b4524" '
        f'text-anchor="middle">o</text>'
        f'<text class="{seen}" x="{num(round(x, 1))}" y="{num(round(y + 4, 1))}" font-size="13" '
        f'font-weight="700" fill="{lit_col}" text-anchor="middle">@</text>'
        f'<text x="{num(round(lx, 1))}" y="{num(round(ly, 1))}" font-size="10" fill="#6e5840" '
        f'text-anchor="{anchor}" letter-spacing=".5" stroke="{BG}" stroke-width="4" '
        f'paint-order="stroke">{ip}</text>'
    )

# ----------------------------------------------------------------- right side

TX = 760
title_svg = pixel_blocks(
    "RECON", TX, 150, 15, [(0, "#fff0d2"), (0.6, "#ffc562"), (1, "#f08a24")], shadow="#3a1c0a"
)

readout = [
    f'<text x="{TX}" y="346" font-size="12" fill="{FAINT}" letter-spacing="1.5">SUMMARY.HOSTS[]</text>'
]
for i, (_node, ip, status, svc) in enumerate(HOSTS):
    lg = legs[i]
    shown = windows([((lg["t0"] + 0.25) / T, 0.995)])
    y = 372 + i * 19
    col = INK if status == "up" else "#c96a45"
    readout.append(
        f'<g class="{shown}" font-size="13">'
        f'<text x="{TX}" y="{y}" fill="{col}">{ip}</text>'
        f'<text x="{TX + 118}" y="{y}" fill="{DIM}">{status}</text>'
        f'<text x="{TX + 168}" y="{y}" fill="#d9a35c">{escape(svc)}</text></g>'
    )
reading = []
for i, lg in enumerate(legs):
    cur = windows([(lg["t0"] / T, (lg["t0"] + lg["pause"]) / T)])
    y = 372 + i * 19
    reading.append(
        f'<text class="{cur}" x="{TX - 16}" y="{y}" font-size="13" fill="#ffc562">&gt;</text>'
    )

sky = Layer()
stars(
    sky,
    W,
    H,
    200,
    seed=4,
    avoid=lambda x, y: (x > 720 and 90 < y < 470) or (60 < y < 470 and x < 720),
)
sky.items = [(x, y, c, mix(BG, "#8f4312", 0.55), cls) for x, y, c, _, cls in sky.items]

css.append(
    ".tw1{animation:tw 4.1s ease-in-out infinite}"
    ".tw2{animation:tw 5.3s ease-in-out -1.7s infinite}"
    ".tw3{animation:tw 6.7s ease-in-out -3.2s infinite}"
    "@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}"
    ".gw,.gi{visibility:hidden}.gi:first-child{visibility:visible}}"
)

body = f"""
<rect width="{W}" height="{H}" fill="{BG}"/>
<defs>
  <radialGradient id="warmth" cx="{CX}" cy="{CY}" r="300" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#f08a24" stop-opacity=".10"/>
    <stop offset="1" stop-color="#8f4312" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="body-glow">
    <stop offset="0" stop-color="#f08a24" stop-opacity=".22"/>
    <stop offset="1" stop-color="#f08a24" stop-opacity="0"/>
  </radialGradient>
</defs>
<ellipse cx="{CX}" cy="{CY}" rx="360" ry="220" fill="url(#warmth)"/>
<g font-size="10">{sky.svg()}</g>
<g font-size="11" font-weight="700">{web.svg()}{"".join(walked)}</g>
<g>{"".join(nodes)}</g>

<g class="crawl">
  <ellipse cx="10" cy="0" rx="62" ry="48" fill="url(#body-glow)"/>
  <g font-size="{GLYPH_SIZE}" font-weight="700" text-anchor="middle">
    <g class="{walk_cls}">{walk_svg}</g>
    <g class="{idle_cls}">{idle_svg}</g>
  </g>
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
{"".join(reading)}

<line x1="40" y1="{H - 46}" x2="{W - 40}" y2="{H - 46}" stroke="{FAINT}" stroke-width="1"/>
<g font-size="12" fill="{DIM}" letter-spacing="1.5">
  <text x="40" y="{H - 22}">walks the scan host by host. nothing invented.</text>
  <text x="{W - 40}" y="{H - 22}" text-anchor="end">python . langgraph . synthetic data only</text>
</g>
"""

svg = svg_doc(
    W,
    H,
    "Recon Summarization Agent",
    "An ASCII spider walks a web whose nodes are scanned hosts, stopping at each one, "
    "while a summary of each host appears next to the project name.",
    body,
    "".join(css),
)
out = ROOT / "assets" / "banner.svg"
out.write_text(svg, encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} ({len(svg) // 1024} KB, loop {T:.2f}s)")
