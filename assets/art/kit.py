"""Shared helpers for the README artwork.

Every picture in assets/ is drawn with text glyphs placed one by one, so the
art is plain SVG text: it scales, stays sharp, and needs no fonts beyond the
system monospace. Glyphs are taken from the agent's own source files.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"

BG = "#03101a"
INK = "#e2f7f1"
DIM = "#6f939a"
FAINT = "#163440"

# One ocean palette for every picture: deep navy, teal, seafoam, foam white.
SEA = [
    (0.00, "#03141d"),
    (0.20, "#06303b"),
    (0.40, "#0b5a62"),
    (0.60, "#14908c"),
    (0.78, "#3fc6b0"),
    (0.90, "#9ee8d4"),
    (1.00, "#f0fffa"),
]
IRIS = SEA
SUNSET = [  # title and progress gradient: foam to teal
    (0.00, "#f0fffa"),
    (0.40, "#9ee8d4"),
    (0.75, "#3fc6b0"),
    (1.00, "#14908c"),
]
SAND = "#f0d49a"  # the one warm accent: highlights, the human gate
GOLD = SAND
TEAL = "#bdeee1"  # "ok" and "clean" lines
PINK = SAND  # flagged lines
LIME = "#c8f5e8"
RED = "#ff6f61"  # failure only (coral)


# --------------------------------------------------------------------------
# colour


def hex2rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb2hex(c: tuple[float, float, float], step: int = 12) -> str:
    """Quantise a little so neighbouring glyphs share a <text> element."""
    out = []
    for v in c:
        n = round(max(0.0, min(1.0, v)) * 255 / step) * step
        out.append(min(255, n))
    return "#{:02x}{:02x}{:02x}".format(*tuple(out))


def mix(a: str, b: str, t: float) -> str:
    ra, rb = hex2rgb(a), hex2rgb(b)
    return rgb2hex(tuple(x + (y - x) * t for x, y in zip(ra, rb, strict=False)))  # type: ignore[arg-type]


def ramp(stops: list[tuple[float, str]], t: float) -> str:
    t = max(0.0, min(1.0, t))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:], strict=False):
        if t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0)
    return stops[-1][1]


def smoothstep(a: float, b: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# glyph sources


_LIGHT = set(".,:;'`-_~\"")
_MID = set("()[]{}<>=+/\\|!?ilrtcjf*^")


def _bucket(c: str) -> int | None:
    if c.isspace() or not c.isprintable() or ord(c) > 126:
        return None
    if c in _LIGHT:
        return 0
    if c in _MID:
        return 1
    if c in "@#%$&80BMWQ":
        return 3
    return 2


class CodeInk:
    """Hands out characters from real source files, sorted by visual weight."""

    def __init__(self, *files: str) -> None:
        text = "".join((ROOT / f).read_text(encoding="utf-8") for f in files)
        self.pools: list[list[str]] = [[], [], [], []]
        for c in text:
            b = _bucket(c)
            if b is not None:
                self.pools[b].append(c)
        self.pos = [0, 0, 0, 0]

    def take(self, weight: int) -> str:
        pool = self.pools[weight]
        c = pool[self.pos[weight] % len(pool)]
        self.pos[weight] += 1
        return c

    def for_value(self, v: float) -> str:
        if v < 0.22:
            return self.take(0)
        if v < 0.48:
            return self.take(1)
        if v < 0.86:
            return self.take(2)
        return self.take(3)


# --------------------------------------------------------------------------
# glyph layer


def num(x: float) -> str:
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


class Layer:
    """A bag of positioned glyphs, written out as compact <text> runs."""

    def __init__(self) -> None:
        self.items: list[tuple[float, float, str, str, str]] = []

    def add(self, x: float, y: float, ch: str, color: str, cls: str = "") -> None:
        if ch and not ch.isspace():
            self.items.append((x, y, ch, color, cls))

    def text(self, x: float, y: float, s: str, color: str, step: float, cls: str = "") -> None:
        for i, ch in enumerate(s):
            self.add(x + i * step, y, ch, color, cls)

    def svg(self) -> str:
        runs: dict[tuple[float, str, str], list[tuple[float, str]]] = defaultdict(list)
        for x, y, ch, color, cls in self.items:
            runs[(y, color, cls)].append((x, ch))
        out = []
        for (y, color, cls), glyphs in sorted(runs.items()):
            glyphs.sort()
            xs = " ".join(num(x) for x, _ in glyphs)
            chars = "".join(escape(c, quote=False) for _, c in glyphs)
            klass = f' class="{cls}"' if cls else ""
            out.append(f'<text x="{xs}" y="{num(y)}" fill="{color}"{klass}>{chars}</text>')
        return "\n".join(out)


def stars(layer: Layer, w: float, h: float, n: int, seed: int, avoid=None) -> None:
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.uniform(8, w - 8), rnd.uniform(8, h - 8)
        if avoid and avoid(x, y):
            continue
        ch = rnd.choice("..........,'`+*")
        col = rnd.choice([FAINT, FAINT, "#4b4670", "#5a4f86", "#2f6f73"])
        cls = rnd.choice(["", "", "", "tw1", "tw2", "tw3"])
        layer.add(round(x, 1), round(y, 1), ch, col, cls)


TWINKLE_CSS = """
.tw1{animation:tw 3.1s ease-in-out infinite}
.tw2{animation:tw 4.3s ease-in-out -1.7s infinite}
.tw3{animation:tw 5.7s ease-in-out -3.2s infinite}
@keyframes tw{0%,100%{opacity:1}50%{opacity:.2}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


# --------------------------------------------------------------------------
# 5x7 pixel font for display words

FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    " ": ["00000"] * 7,
}


def pixel_word(
    layer: Layer,
    word: str,
    x0: float,
    y0: float,
    px: float,
    py: float,
    ink: CodeInk,
    colors: list[tuple[float, str]],
    sub: int = 2,
    shadow: str | None = None,
) -> float:
    """Draw a word in the 5x7 font; every pixel is a sub x 1 block of glyphs."""
    cw = px / sub
    x = x0
    cells = []
    for letter in word:
        rows = FONT[letter]
        for r, row in enumerate(rows):
            for c, bit in enumerate(row):
                if bit == "1":
                    for s in range(sub):
                        cells.append((x + c * px + s * cw, y0 + r * py, r))
        x += 6 * px
    if shadow:
        for cx, cy, _ in cells:
            layer.add(cx + cw * 0.9, cy + py * 0.32, ink.take(2), shadow)
    for cx, cy, r in cells:
        layer.add(cx, cy, ink.take(3 if r % 3 else 2), ramp(colors, r / 6))
    return x - px


def pixel_blocks(
    word: str,
    x0: float,
    y0: float,
    px: float,
    colors: list[tuple[float, str]],
    shadow: str | None = None,
    gap: float = 1.6,
) -> str:
    """A word in the 5x7 font as crisp square pixels with an offset shadow."""
    front, back = [], []
    x = x0
    for letter in word:
        for r, row in enumerate(FONT[letter]):
            for c, bit in enumerate(row):
                if bit != "1":
                    continue
                X, Y, S = x + c * px, y0 + r * px, px - gap
                back.append(
                    f'<rect x="{num(X + px * 0.4)}" y="{num(Y + px * 0.4)}" width="{num(S)}" height="{num(S)}"/>'
                )
                front.append(
                    f'<rect x="{num(X)}" y="{num(Y)}" width="{num(S)}" height="{num(S)}" fill="{ramp(colors, r / 6)}"/>'
                )
        x += 6 * px
    out = ""
    if shadow:
        out += f'<g fill="{shadow}">' + "".join(back) + "</g>"
    return out + "<g>" + "".join(front) + "</g>"


def png_data_uri(pixels: list[list[tuple[int, ...]]]) -> str:
    """Encode rows of RGB or RGBA tuples as a base64 PNG data URI (no dependencies)."""
    import base64
    import struct
    import zlib

    h, w = len(pixels), len(pixels[0])
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in pixels)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(
        b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if len(pixels[0][0]) == 4 else 2, 0, 0, 0)
    )
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def box_blur(grid: list[list[float]], radius: int, passes: int = 3) -> list[list[float]]:
    """Approximate Gaussian blur of a 2D float grid."""
    h, w = len(grid), len(grid[0])
    for _ in range(passes):
        out = []
        for row in grid:
            acc, line = 0.0, []
            pref = [0.0]
            for v in row:
                acc += v
                pref.append(acc)
            for x in range(w):
                a, b = max(0, x - radius), min(w, x + radius + 1)
                line.append((pref[b] - pref[a]) / (b - a))
            out.append(line)
        grid = out
        cols = []
        for x in range(w):
            acc, pref = 0.0, [0.0]
            for y in range(h):
                acc += grid[y][x]
                pref.append(acc)
            cols.append(pref)
        grid = [
            [
                (cols[x][min(h, y + radius + 1)] - cols[x][max(0, y - radius)])
                / (min(h, y + radius + 1) - max(0, y - radius))
                for x in range(w)
            ]
            for y in range(h)
        ]
    return grid


def svg_doc(w: int, h: int, title: str, desc: str, body: str, css: str = "") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">
<title id="t">{escape(title)}</title>
<desc id="d">{escape(desc)}</desc>
<style>
text{{font-family:{MONO};white-space:pre}}
{css}
</style>
{body}
</svg>
"""


def polar(x: float, y: float) -> tuple[float, float]:
    return math.hypot(x, y), math.atan2(y, x)


# --------------------------------------------------------------------------
# diagram helpers


def box(
    layer: Layer, x: float, y: float, cols: int, rows: int, color: str, cw: float, ch: float
) -> None:
    """A box-drawing frame whose top-left glyph sits at (x, y), baseline coordinates."""
    for c in range(cols):
        top = "┌" if c == 0 else ("┐" if c == cols - 1 else "─")
        bot = "└" if c == 0 else ("┘" if c == cols - 1 else "─")
        layer.add(x + c * cw, y, top, color)
        layer.add(x + c * cw, y + (rows - 1) * ch, bot, color)
    for r in range(1, rows - 1):
        layer.add(x, y + r * ch, "│", color)
        layer.add(x + (cols - 1) * cw, y + r * ch, "│", color)


def show_window(name: str, a: float, b: float, fade: float = 0.012, peak: float = 1.0) -> str:
    """CSS keyframes that keep an element visible between fractions a and b of the loop."""
    pts = {0.0: 0.0, 1.0: 0.0}
    pts[max(0.0, a - fade)] = 0.0 if a - fade > 0 else peak
    pts[max(0.0, a)] = peak
    pts[min(1.0, b)] = peak
    if b + fade < 1:
        pts[b + fade] = 0.0
    else:
        pts[1.0] = peak if b >= 1 else 0.0
    if a <= 0:
        pts[0.0] = peak
    frames = "".join(f"{p * 100:.2f}%{{opacity:{o:g}}}" for p, o in sorted(pts.items()))
    return f"@keyframes {name}{{{frames}}}"
