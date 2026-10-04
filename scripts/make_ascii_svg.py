#!/usr/bin/env python3
"""Convert source-prepped.png into a self-typing colour ASCII portrait SVG.

source-prepped.png is RGBA (see prep_photo.py): transparent pixels print as
nothing. Every other cell of a downsampled, sharpened grid picks a glyph
from a density ramp by brightness – on the dark terminal, bright areas (skin,
shirt, headphones) get dense glyphs, dark ones (hair, laptop) a lighter
texture – and is drawn in the photo's own colour for that cell, lifted and
saturated a bit so dark tones still read on #0d1117.

Animation is pure SMIL: every row sits behind a horizontal clip that wipes
left-to-right with a block cursor riding the edge, staggered top to bottom.
Prints once, then freezes – GitHub plays SMIL inside <img>-embedded SVGs.

    python scripts/make_ascii_svg.py            # writes jachym-ascii.svg
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""

import colorsys
import os
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "jachym-ascii.svg"

# sparse -> dense; index 0 (space) is reserved for the transparent background
RAMP = " .`'-:;~=+*cxsoO#%&@"
GAMMA = 0.85    # <1 pushes midtones up the ramp so the subject reads solid
MIN_GLYPH = 11   # densest-floor inside the silhouette, so it never has holes
SHARPEN = 110   # unsharp % at grid size

COLS = 144
FONT_SIZE = 8.5
CW = 5.0   # advance width forced via textLength
CH = 8.5    # line height

PAD = 18
BG = "#0d1117"
BORDER = "#30363d"
CURSOR = "#c9d1d9"

# Colour treatment on a dark background (HSV value/saturation, 0..1).
MIN_V = 0.12     # lift near-black (hair, laptop) so it is visible at all
SAT_BOOST = 1.5
Q = 12           # per-channel quantisation step; keeps <tspan> runs long

ROW_STAGGER = 0.035  # s between row starts
ROW_DUR = 0.5        # s for one row wipe
START = 0.3          # s initial delay


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tint(r: float, g: float, b: float) -> str:
    h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    sat = min(1.0, sat * SAT_BOOST)
    v = MIN_V + (1 - MIN_V) * v
    rgb = colorsys.hsv_to_rgb(h, sat, v)
    return "#%02x%02x%02x" % tuple(min(255, round(c * 255 / Q) * Q) for c in rgb)


def main() -> None:
    static = os.environ.get("STATIC") == "1"

    src = Image.open(SRC).convert("RGBA")
    src = src.crop(src.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox())
    rows = round(src.height / src.width * COLS * (CW / CH))

    # Premultiply onto black before downsampling so edge cells don't pick up
    # whatever colour the matte hid, then un-premultiply per cell.
    alpha = src.getchannel("A")
    rgb = Image.composite(src.convert("RGB"), Image.new("RGB", src.size), alpha)
    rgb = rgb.resize((COLS, rows), Image.BOX)
    alpha = alpha.resize((COLS, rows), Image.BOX)
    # Sharpen at the target grid so eyes, the headphone band and the collar
    # survive the downsample.
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.0, percent=SHARPEN, threshold=3))
    cpx, apx = rgb.load(), alpha.load()

    # Stretch brightness over the subject only (1st..99th percentile).
    lum = {}
    for r in range(rows):
        for c in range(COLS):
            a = apx[c, r]
            if a >= 128:
                R, G, B = (v * 255 / a for v in cpx[c, r])
                lum[c, r] = (0.299 * R + 0.587 * G + 0.114 * B, (R, G, B))
    ls = sorted(v for v, _ in lum.values())
    lo, hi = ls[len(ls) // 100], ls[-len(ls) // 100 - 1]

    grid_w = COLS * CW
    width = grid_w + 2 * PAD
    height = rows * CH + 2 * PAD

    # Each line is a list of (colour, text) runs; trailing blanks dropped.
    n = len(RAMP) - 1
    lines = []
    for r in range(rows):
        cells = []
        for c in range(COLS):
            if (c, r) not in lum:
                cells.append((0, None))
                continue
            v, col = lum[c, r]
            v = min(max((v - lo) / (hi - lo), 0.0), 1.0) ** GAMMA
            cells.append((MIN_GLYPH + round(v * (n - MIN_GLYPH)), tint(*col)))
        while cells and cells[-1][0] == 0:
            cells.pop()
        runs = []
        for idx, fill in cells:
            ch = RAMP[idx]
            if runs and (fill is None or runs[-1][0] in (fill, None)):
                prev, text = runs[-1]
                runs[-1] = (prev if fill is None else fill, text + ch)
            else:
                runs.append((fill, ch))
        lines.append(runs)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="ASCII portrait of Jáchym Šolta">'
    )
    svg.append(
        f'<rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1:.0f}" '
        f'rx="12" fill="{BG}" stroke="{BORDER}"/>'
    )

    if not static:
        svg.append("<defs>")
        for r, runs in enumerate(lines):
            if not runs:
                continue
            t = START + r * ROW_STAGGER
            svg.append(
                f'<clipPath id="c{r}"><rect x="{PAD}" y="{PAD + r * CH:.1f}" width="0" height="{CH}">'
                f'<animate attributeName="width" from="0" to="{grid_w:.0f}" '
                f'begin="{t:.2f}s" dur="{ROW_DUR}s" fill="freeze"/></rect></clipPath>'
            )
        svg.append("</defs>")

    svg.append(
        f'<g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
        f'font-size="{FONT_SIZE}">'
    )
    for r, runs in enumerate(lines):
        if not runs:
            continue
        length = sum(len(t) for _, t in runs)
        clip = "" if static else f' clip-path="url(#c{r})"'
        spans = "".join(f'<tspan fill="{f}">{esc(t)}</tspan>' for f, t in runs)
        # textLength pins the advance width so the grid stays aligned in any font.
        svg.append(
            f'<text x="{PAD}" y="{PAD + (r + 1) * CH - 1.8:.1f}" xml:space="preserve" '
            f'textLength="{length * CW:.1f}" lengthAdjust="spacingAndGlyphs"{clip}>{spans}</text>'
        )
    svg.append("</g>")

    if not static:
        for r, runs in enumerate(lines):
            if not runs:
                continue
            t = START + r * ROW_STAGGER
            end = t + ROW_DUR
            svg.append(
                f'<rect x="{PAD}" y="{PAD + r * CH + 1:.1f}" width="{CW:.1f}" height="{CH - 2:.1f}" '
                f'fill="{CURSOR}" opacity="0">'
                f'<set attributeName="opacity" to="0.9" begin="{t:.2f}s"/>'
                f'<animate attributeName="x" from="{PAD}" to="{PAD + grid_w:.1f}" '
                f'begin="{t:.2f}s" dur="{ROW_DUR}s" fill="freeze"/>'
                f'<set attributeName="opacity" to="0" begin="{end:.2f}s"/>'
                f"</rect>"
            )

    svg.append("</svg>")
    OUT.write_text("\n".join(svg), encoding="utf-8")
    print(f"wrote {OUT} ({COLS}x{rows} chars, {width:.0f}x{height:.0f}px)")


if __name__ == "__main__":
    main()
