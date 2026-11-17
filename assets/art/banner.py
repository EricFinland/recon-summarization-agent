"""Top banner: an eye drawn with the agent's own source code.

Run from the repo root:  python assets/art/banner.py
Writes assets/banner.svg.

The eye is a brightness field (iris fibres, crypts, collarette, eyelid fold,
lashes, waterline, catchlight) sampled on a fine character grid. Brightness
picks both the glyph weight and its colour on one warm ramp.
"""

from __future__ import annotations

import math
import random

from kit import (
    BG,
    DIM,
    FAINT,
    INK,
    ROOT,
    WARM,
    CodeInk,
    Layer,
    box_blur,
    hex2rgb,
    mix,
    pixel_blocks,
    png_data_uri,
    ramp,
    smoothstep,
    stars,
    svg_doc,
)

W, H = 1280, 480
CX, CY = 372, 252  # centre of the eye opening
EW = 300  # half width of the opening
UP, LO = 104, 86  # lid heights above and below the centre
IX, IY = 10, -4  # iris centre, relative to the opening
R, RP = 104, 35  # iris and pupil radius
CW, CH = 3.3, 4.7  # glyph cell: about four times finer than a normal terminal
FONT_SIZE = 5.9
SPAN_X, SPAN_Y = 352, 190  # area of the drawing around the eye

rnd = random.Random(21)
ink = CodeInk(
    "src/recon_agent/summarizer.py",
    "src/recon_agent/validator.py",
    "src/recon_agent/sanitizer.py",
)
ink_alt = CodeInk("src/recon_agent/loader.py", "src/recon_agent/pipeline.py")


# ----------------------------------------------------------------- noise


def _hash(i: int, j: int, seed: int) -> float:
    h = (i * 374761393 + j * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 0xFFFFFFFF


def noise(x: float, y: float, seed: int, wrap: int = 0) -> float:
    """Smooth value noise; wrap > 0 makes it periodic in x."""
    i, j = math.floor(x), math.floor(y)
    fx, fy = x - i, y - j
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def h(a: int, b: int) -> float:
        return _hash(a % wrap if wrap else a, b, seed)

    top = h(i, j) * (1 - fx) + h(i + 1, j) * fx
    bot = h(i, j + 1) * (1 - fx) + h(i + 1, j + 1) * fx
    return top * (1 - fy) + bot * fy


def fbm(x: float, y: float, seed: int, octaves: int = 4) -> float:
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * noise(x * 2**o, y * 2**o, seed + o)
        norm += amp
        amp *= 0.5
    return total / norm


# ----------------------------------------------------------------- shape


def upper(dx: float) -> float:
    t = max(0.0, 1 - (dx / EW) ** 2)
    return -UP * t**0.72 * (1 + 0.12 * dx / EW)


def lower(dx: float) -> float:
    t = max(0.0, 1 - (dx / EW) ** 2)
    return LO * t**1.25 * (1 - 0.06 * dx / EW)


def crease(dx: float) -> float:
    return upper(dx) * 1.42 - 14 * max(0.0, 1 - (dx / (EW * 1.15)) ** 2)


# ----------------------------------------------------------------- iris

FIBRES = 260


def iris(x: float, y: float) -> float:
    r = math.hypot(x, y)
    a = math.atan2(y, x)
    rn = (r - RP) / (R - RP)
    turn = (a / (2 * math.pi)) % 1

    # pupil ruff: a beaded rim right at the pupil edge
    if rn < 0.035:
        return 0.55 + 0.4 * (0.5 + 0.5 * math.sin(a * 46))

    # fibres: fast across the angle, slow along the radius, a little wavy
    u = turn * FIBRES + 2.5 * (noise(turn * 9, rn * 2.5, 3, wrap=9) - 0.5)
    fib = 0.62 * noise(u, rn * 5.5, 7, wrap=FIBRES)
    fib += 0.38 * noise(u * 0.4, rn * 2.5, 9, wrap=int(FIBRES * 0.4))
    fib = fib**1.35

    # collarette: a zigzag ring that splits the iris into two zones
    rc = 0.34 + 0.035 * math.sin(a * 13 + 0.7) + 0.05 * (noise(turn * 24, 0.5, 4, wrap=24) - 0.5)
    collar = math.exp(-(((rn - rc) / 0.04) ** 2))

    if rn < rc:  # pupillary zone: finer, brighter, warmer
        v = 0.42 + 0.42 * fib + 0.12 * (1 - rn / rc)
    else:  # ciliary zone
        v = 0.26 + 0.6 * fib

    # crypts: dark lacunae scattered through the ciliary zone
    cr = noise(turn * 34, rn * 4.2, 13, wrap=34)
    band = smoothstep(rc + 0.02, rc + 0.12, rn) * (1 - smoothstep(0.62, 0.78, rn))
    v *= 1 - 0.8 * smoothstep(0.6, 0.76, cr) * band

    # contraction furrows: broken concentric dark arcs near the edge
    furrow = sum(math.exp(-(((rn - c) / 0.016) ** 2)) for c in (0.69, 0.81))
    v *= 1 - 0.55 * furrow * smoothstep(0.35, 0.65, noise(turn * 7, 0.5, 17, wrap=7))

    v += 0.42 * collar * (0.6 + 0.4 * fib)

    # limbal ring and light from the upper left
    v *= 1 - 0.9 * smoothstep(0.82, 1.0, rn)
    v *= 0.82 + 0.28 * max(0.0, math.cos(a - math.radians(-135)))
    return v


# ----------------------------------------------------------------- field


def field(dx: float, dy: float) -> tuple[float, str]:
    """Brightness at a point and the part of the eye it belongs to."""
    top, bot = upper(dx), lower(dx)
    ax = abs(dx) / EW

    # outside the drawing: fade to black
    e = (dx / (EW * 1.1)) ** 2 + ((dy + 8) / (UP * 1.6)) ** 2
    fade = 1 - smoothstep(0.5, 1.0, e)
    if fade <= 0:
        return 0.0, "skin"

    skin_tex = 0.82 + 0.36 * fbm(dx / 9, dy / 6, 31, 3)

    if dy < top - 1.5:  # upper lid and brow
        cz = crease(dx)
        if dy > cz:  # the lid fold: rounded, catches light in the middle
            t = (dy - cz) / max(1.0, top - cz)
            v = 0.30 + 0.20 * math.sin(math.pi * min(1, t)) * (1 - 0.6 * ax)
            v -= 0.25 * smoothstep(0.82, 1.0, t)  # lash line shadow
        else:  # above the crease
            v = 0.16 * (1 - smoothstep(0, 40, cz - dy)) * (1 - ax)
        v *= 1 - 0.75 * math.exp(-(((dy - cz) / 4.5) ** 2))  # crease groove
        if abs(dy - top) < 3.2:  # lid margin
            v = 0.72 - 0.25 * ax
        return max(0.0, v * skin_tex * fade), "skin"

    if dy > bot + 1.5:  # lower lid and cheek
        d = dy - bot
        v = 0.06 + 0.16 * math.exp(-(((d - 18) / 10) ** 2)) * (1 - ax)
        v *= 1 - 0.5 * math.exp(-(((d - 40) / 6) ** 2))
        if d < 4.5:  # waterline, wet and bright
            v = 0.40 + 0.22 * (1 - ax) * (0.5 + 0.5 * noise(dx / 5, 0, 41))
        return max(0.0, v * skin_tex * fade), "skin"

    # inside the opening
    edge = min(dy - top, bot - dy)
    lid_shadow = 0.28 + 0.72 * smoothstep(1, 30, dy - top)
    x, y = dx - IX, dy - IY
    r = math.hypot(x, y)

    if r < RP:
        return 0.0, "pupil"

    if r < R:
        v = 1.3 * iris(x, y) * lid_shadow
        v *= 0.55 + 0.45 * smoothstep(0, 5, edge)
        return v, "iris"

    # caruncle in the inner corner
    car = ((dx + EW - 26) / 20) ** 2 + ((dy - 6) / 13) ** 2
    if car < 1:
        return 0.24 + 0.22 * fbm(dx / 4, dy / 4, 51, 2) * (1 - car), "skin"

    # sclera: a lit sphere, shadowed by the lid, with faint veins
    v = 0.34 * (0.72 + 0.28 * (1 - (dx / (EW * 1.05)) ** 2))
    v *= lid_shadow
    v *= 1 - 0.6 * smoothstep(0.55, 1.0, ax)
    v *= 1 - 0.38 * math.exp(-(((r - R) / 7) ** 2))  # shadow ring round the iris
    ridge = 1 - abs(2 * fbm(dx / 22, dy / 14, 61, 3) - 1)
    v *= 1 - 0.45 * smoothstep(0.9, 0.97, ridge) * smoothstep(0.35, 0.8, ax)
    v *= 0.9 + 0.2 * noise(dx / 3, dy / 3, 71)
    v *= 0.5 + 0.5 * smoothstep(0, 6, edge)
    return v, "sclera"


# ----------------------------------------------------------------- render

eye = Layer()
alt = Layer()  # second set of glyphs for the iris; the two cross-fade
grid: dict[tuple[int, int], tuple[float, str]] = {}

cols = int(2 * SPAN_X / CW)
rows = int(2 * SPAN_Y / CH)
for j in range(rows):
    for i in range(cols):
        grid[(i, j)] = field(-SPAN_X + i * CW, -SPAN_Y + j * CH)


def cell(px: float, py: float) -> tuple[int, int]:
    return round((px + SPAN_X) / CW), round((py + SPAN_Y) / CH)


overrides: dict[tuple[int, int], tuple[float, str]] = {}


def stroke_char(ang: float) -> str:
    if 68 < ang < 112:
        return "|"
    if 22 < ang <= 68:
        return "/"
    if 112 <= ang < 158:
        return "\\"
    return "-"


def stroke(points: list[tuple[float, float]], v0: float, v1: float) -> None:
    for n, (px, py) in enumerate(points):
        if n + 1 < len(points):
            qx, qy = points[n + 1]
        else:
            qx, qy = px + (px - points[n - 1][0]), py + (py - points[n - 1][1])
        ang = math.degrees(math.atan2(-(qy - py), qx - px)) % 180
        v = v0 + (v1 - v0) * n / max(1, len(points) - 1)
        key = cell(px, py)
        if key not in overrides or overrides[key][0] < v:
            overrides[key] = (v, stroke_char(ang))


# upper lashes: dense, curling up and toward the outer corner
for k in range(84):
    t = -0.92 + 1.84 * (k + rnd.uniform(-0.3, 0.3)) / 83
    dx0 = t * EW
    x, y = dx0, upper(dx0) - 2
    length = 20 + 22 * (1 - abs(t)) ** 0.6 + rnd.uniform(-5, 5)
    lean = 0.25 + 0.75 * t
    pts = []
    steps = int(length / 2.4)
    for s in range(steps):
        f = s / steps
        x += (lean * 0.9 + 0.5 * f * (1 if t > -0.2 else -1)) * 2.2
        y -= (1.0 - 0.75 * f * f) * 2.4
        pts.append((x, y))
    stroke(pts, 0.8, 0.3)

# lower lashes: short, sparse, pointing down and outward
for k in range(26):
    t = -0.78 + 1.6 * (k + rnd.uniform(-0.3, 0.3)) / 25
    dx0 = t * EW
    x, y = dx0, lower(dx0) + 5
    pts = []
    for s in range(int(3 + 3 * (1 - abs(t)) + rnd.random())):
        x += (0.9 * t + 0.25 * s * t) * 2.4
        y += 1.7
        pts.append((x, y))
    stroke(pts, 0.36, 0.14)

# catchlight: a window reflection with a cross bar, and a small second spark
win_x, win_y = IX - 30, IY - 30
for j in range(-4, 5):
    for i in range(-8, 9):
        px, py = win_x + i * CW, win_y + j * CH
        if abs(i * CW) <= 13 and abs(j * CH) <= 11:
            bar = abs(i * CW) < 1.8 or abs(j * CH) < 1.6
            overrides[cell(px, py)] = (0.45 if bar else 1.0, "")
for px, py in [(IX + 22, IY + 20), (IX + 25, IY + 20), (IX + 22, IY + 25)]:
    overrides[cell(px, py)] = (0.95, "")

for (i, j), (v, part) in grid.items():
    ch = ""
    if (i, j) in overrides:
        v, ch = overrides[(i, j)]
        part = "line"
    if v < 0.1:
        continue
    tone = min(1.0, v * 1.12) ** 0.85
    x = round(CX - SPAN_X + i * CW, 1)
    y = round(CY - SPAN_Y + j * CH, 1)
    color = ramp(WARM, tone)
    glyph = ch or ink.for_value(tone)
    if part == "iris":
        dxr, dyr = x - CX - IX, y - CY - IY
        sector = int(((math.atan2(dyr, dxr) + math.pi) / (2 * math.pi)) * 12) % 12
        eye.add(x, y, glyph, color, f"a{sector}")
        alt.add(x, y, ink_alt.for_value(tone), color, f"b{sector}")
    else:
        eye.add(x, y, glyph, color)


# glow: a blurred copy of the field under the glyphs, like light bleeding
GS = 2.0  # glow sample spacing in px
gw, gh = int(2 * SPAN_X / GS), int(2 * SPAN_Y / GS)
lum = []
for yy in range(gh):
    row = []
    for xx in range(gw):
        dx, dy = -SPAN_X + xx * GS, -SPAN_Y + yy * GS
        v, _ = field(dx, dy)
        if math.hypot(dx - win_x, dy - win_y) < 14:
            v = 1.2
        row.append(max(0.0, min(1.2, v)))
    lum.append(row)
soft = box_blur(lum, 2)
wide = box_blur(lum, 10)
pixels = []
for yy in range(gh):
    prow = []
    for xx in range(gw):
        v = 0.75 * soft[yy][xx] + 0.55 * wide[yy][xx]
        r, g, b = hex2rgb(ramp(WARM, min(1.0, v) ** 0.8))
        k = min(1.0, v * 1.15)
        prow.append((int(r * 255 * k), int(g * 255 * k), int(b * 255 * k)))
    pixels.append(prow)
GLOW = png_data_uri(pixels)


def outside(x: float, y: float) -> bool:
    return (abs(x - CX) < SPAN_X + 10 and abs(y - CY) < SPAN_Y - 10) or (
        720 < x < 1250 and 70 < y < 410
    )


sky = Layer()
stars(sky, W, H, 260, seed=4, avoid=outside)
sky.items = [(x, y, c, mix(BG, "#8f4312", 0.6), cls) for x, y, c, _, cls in sky.items]

# ----------------------------------------------------------------- title side

TX = 760
title_svg = pixel_blocks(
    "RECON", TX, 166, 15, [(0, "#fff0d2"), (0.6, "#ffc562"), (1, "#f08a24")], shadow="#3a1c0a"
)

css = "\n".join(
    [
        "@keyframes fa{0%,45%{opacity:1}48%,95%{opacity:0}98%,100%{opacity:1}}",
        "@keyframes fb{0%,45%{opacity:0}48%,95%{opacity:1}98%,100%{opacity:0}}",
        *(f".a{k}{{animation:fa 12s ease-in-out {-k}s infinite}}" for k in range(12)),
        *(f".b{k}{{animation:fb 12s ease-in-out {-k}s infinite}}" for k in range(12)),
        ".tw1{animation:tw 4.1s ease-in-out infinite}",
        ".tw2{animation:tw 5.3s ease-in-out -1.7s infinite}",
        ".tw3{animation:tw 6.7s ease-in-out -3.2s infinite}",
        "@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}",
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}"
        + ",".join(f".b{k}" for k in range(12))
        + "{opacity:0}}",
    ]
)

body = f"""
<rect width="{W}" height="{H}" fill="{BG}"/>
<defs>
  <radialGradient id="warmth" cx="{CX + IX}" cy="{CY + IY}" r="330" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#f08a24" stop-opacity=".16"/>
    <stop offset=".5" stop-color="#8f4312" stop-opacity=".06"/>
    <stop offset="1" stop-color="#8f4312" stop-opacity="0"/>
  </radialGradient>
</defs>
<ellipse cx="{CX + IX}" cy="{CY + IY}" rx="380" ry="230" fill="url(#warmth)"/>
<g font-size="10">
{sky.svg()}
</g>
<image href="{GLOW}" x="{CX - SPAN_X}" y="{CY - SPAN_Y}" width="{2 * SPAN_X}" height="{2 * SPAN_Y}" opacity=".42" preserveAspectRatio="none"/>
<g font-size="{FONT_SIZE}" font-weight="700">
{eye.svg()}
{alt.svg()}
</g>

<g font-size="12" fill="{DIM}" letter-spacing="2">
  <text x="40" y="44">01 / 04</text>
  <text x="{W - 40}" y="44" text-anchor="end">SCAN IN . SUMMARY OUT</text>
</g>
<line x1="40" y1="58" x2="{W - 40}" y2="58" stroke="{FAINT}" stroke-width="1"/>

<rect x="{TX}" y="118" width="214" height="28" fill="{INK}"/>
<text x="{TX + 12}" y="137" font-size="13" fill="{BG}" letter-spacing="1.5">AGENT 01 . PENTEST POC</text>

{title_svg}

<text x="{TX}" y="318" font-size="25" fill="{INK}" letter-spacing="5">summarization agent</text>
<text x="{TX}" y="356" font-size="14" fill="{DIM}">reads a synthetic scan, writes a summary</text>
<text x="{TX}" y="378" font-size="14" fill="{DIM}">the next agent can trust. nothing invented.</text>

<line x1="40" y1="{H - 46}" x2="{W - 40}" y2="{H - 46}" stroke="{FAINT}" stroke-width="1"/>
<g font-size="12" fill="{DIM}" letter-spacing="1.5">
  <text x="40" y="{H - 22}">drawn with its own source code</text>
  <text x="{W - 40}" y="{H - 22}" text-anchor="end">python . langgraph . synthetic data only</text>
</g>
"""

svg = svg_doc(
    W,
    H,
    "Recon Summarization Agent",
    "A detailed eye drawn in warm amber source-code characters next to the project name. "
    "The characters in the iris slowly change, like live code.",
    body,
    css,
)
out = ROOT / "assets" / "banner.svg"
out.write_text(svg, encoding="utf-8")
glyphs = len(eye.items) + len(alt.items)
print(f"wrote {out.relative_to(ROOT)} ({len(svg) // 1024} KB, {glyphs} glyphs)")
