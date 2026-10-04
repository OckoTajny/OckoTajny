#!/usr/bin/env python3
"""Convert source-prepped.png into a self-typing ASCII portrait SVG.

Each pixel of a downsampled, sharpened grid picks a glyph from a density
ramp – sparse characters for bright areas, dense for dark. Colour comes from a
diagonal cyan -> blue -> purple -> coral gradient (the info card's accents),
dimmed per glyph by density so shading reads twice. The background is washed
to white upstream; it is flood-filled from the border here and prints as
nothing, while everything inside the silhouette gets at least a dot.

Animation is pure SMIL: every row sits behind a horizontal clip that wipes
left-to-right with a block cursor riding the edge, staggered top to bottom.
Prints once, then freezes – GitHub plays SMIL inside <img>-embedded SVGs.

    python scripts/make_ascii_svg.py            # writes jachym-ascii.svg
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "jachym-ascii.svg"

# bright (sparse) -> dark (dense); the leading space clears the background
RAMP = " .`'-:;~=+*cxsoO#%&@"
GAMMA = 1.2  # >1 darkens midtones so the face gets denser glyphs
BLUR = 1.2      # px, pre-downsample grain removal
SHARPEN = 120   # unsharp % at grid size
BG_WHITE = 250  # source pixels this bright and connected to the border = background

COLS = 110
FONT_SIZE = 11
CW = 6.5   # advance width forced via textLength
CH = 11    # line height

PAD = 18
BG = "#0d1117"
BORDER = "#30363d"
CURSOR = "#c9d1d9"

# Diagonal hue gradient (top-left -> bottom-right), same accents as the info
# card: cyan -> blue -> purple -> coral. Each glyph's colour is then dimmed by
# how sparse it is, so shading reads in brightness as well as density.
STOPS = ["#76e3ea", "#58a6ff", "#bc8cff", "#ff7b72"]
HUE_STEPS = 24   # quantisation keeps adjacent glyphs in shared <tspan> runs
LUM_STEPS = 5
DIM_FLOOR = 0.45  # brightness of the sparsest glyph relative to full colour

ROW_STAGGER = 0.035  # s between row starts
ROW_DUR = 0.5        # s for one row wipe
START = 0.3          # s initial delay


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def hex_rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def gradient(t: float) -> tuple[float, float, float]:
    stops = [hex_rgb(h) for h in STOPS]
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    return tuple(a + (b - a) * f for a, b in zip(stops[i], stops[i + 1]))


def colour(hue_q: int, lum_q: int) -> str:
    base = hex_rgb(BG)
    rgb = gradient(hue_q / (HUE_STEPS - 1))
    k = DIM_FLOOR + (1 - DIM_FLOOR) * lum_q / (LUM_STEPS - 1)
    return "#%02x%02x%02x" % tuple(round(b + (c - b) * k) for b, c in zip(base, rgb))


def main() -> None:
    static = os.environ.get("STATIC") == "1"

    src = Image.open(SRC).convert("L")

    # Subject mask: flood the washed-white background in from the border, so
    # only that (not white highlights inside the subject) prints as nothing.
    bg = src.point(lambda v: 255 if v >= BG_WHITE else 0)
    for x, y in [(0, 0), (bg.width - 1, 0), (0, bg.height - 1), (bg.width - 1, bg.height - 1)]:
        if bg.getpixel((x, y)) == 255:
            ImageDraw.floodfill(bg, (x, y), 128)
    subject = bg.point(lambda v: 0 if v == 128 else 255)

    # Crop to the subject so every column carries detail, not empty margin.
    box = subject.getbbox()
    src, subject = src.crop(box), subject.crop(box)
    rows = round(src.height / src.width * COLS * (CW / CH))

    # Knock down the photo grain, and paint the background mid-grey so edge
    # cells average subject tones instead of bleaching towards white.
    src = src.filter(ImageFilter.GaussianBlur(BLUR))
    img = Image.composite(src, Image.new("L", src.size, 128), subject)
    img = img.resize((COLS, rows), Image.LANCZOS)
    mask = subject.resize((COLS, rows), Image.BOX).point(lambda v: 255 if v >= 128 else 0)
    # Sharpen at the target grid so eyes, hair and the collar survive the
    # downsample, then stretch levels over the subject only.
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=SHARPEN, threshold=3))
    img = ImageOps.autocontrast(img, cutoff=2, mask=mask)
    px, mk = img.load(), mask.load()

    grid_w = COLS * CW
    width = grid_w + 2 * PAD
    height = rows * CH + 2 * PAD

    # Each line is a list of (colour, text) runs; trailing blanks dropped.
    lines = []
    n = len(RAMP) - 1
    for r in range(rows):
        cells = []
        for c in range(COLS):
            if mk[c, r] < 128:
                cells.append(0)
                continue
            # Dark (hair, laptop) -> dense, light (skin, shirt) -> sparse, but
            # never blank inside the subject so the silhouette stays solid.
            v = (px[c, r] / 255) ** GAMMA
            cells.append(1 + round((1 - v) * (n - 1)))
        while cells and cells[-1] == 0:
            cells.pop()
        runs = []
        for c, idx in enumerate(cells):
            ch = RAMP[idx]
            if idx == 0:
                fill = None
            else:
                t = 0.7 * r / max(rows - 1, 1) + 0.3 * c / (COLS - 1)
                hue_q = round(t * (HUE_STEPS - 1))
                lum_q = round(idx / n * (LUM_STEPS - 1))
                fill = colour(hue_q, lum_q)
            if runs and (fill is None or runs[-1][0] == fill or runs[-1][0] is None):
                prev_fill, text = runs[-1]
                runs[-1] = (prev_fill if fill is None else fill, text + ch)
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
                f'<clipPath id="c{r}"><rect x="{PAD}" y="{PAD + r * CH}" width="0" height="{CH}">'
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
            f'<text x="{PAD}" y="{PAD + (r + 1) * CH - 2}" xml:space="preserve" '
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
                f'<rect x="{PAD}" y="{PAD + r * CH + 1}" width="{CW:.1f}" height="{CH - 2}" '
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
