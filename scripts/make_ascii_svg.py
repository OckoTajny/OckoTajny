#!/usr/bin/env python3
"""Convert source-prepped.png into a self-typing ASCII portrait SVG.

Each pixel of a downsampled grid picks a glyph from a density ramp — sparse
characters for bright areas, dense for dark. Two choices keep it clean:
monochrome (one light-gray fill) and high contrast (background washed to
white upstream, so it maps to the leading space and prints as nothing).

Animation is pure SMIL: every row sits behind a horizontal clip that wipes
left-to-right with a block cursor riding the edge, staggered top to bottom.
Prints once, then freezes — GitHub plays SMIL inside <img>-embedded SVGs.

    python scripts/make_ascii_svg.py            # writes jachym-ascii.svg
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""

import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "jachym-ascii.svg"

RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense); space clears the bg
GAMMA = 1.1  # >1 darkens midtones so the face gets denser glyphs; white stays white

COLS = 100
FONT_SIZE = 12
CW = 7.2   # advance width forced via textLength
CH = 12    # line height

PAD = 18
BG = "#0d1117"
BORDER = "#30363d"
INK = "#c9d1d9"
CURSOR = "#58a6ff"

ROW_STAGGER = 0.045  # s between row starts
ROW_DUR = 0.55       # s for one row wipe
START = 0.3          # s initial delay


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    static = os.environ.get("STATIC") == "1"

    img = Image.open(SRC).convert("L")
    rows = round(img.height / img.width * COLS * (CW / CH))
    img = img.resize((COLS, rows), Image.BOX)
    px = img.load()

    grid_w = COLS * CW
    width = grid_w + 2 * PAD
    height = rows * CH + 2 * PAD

    lines = []
    for r in range(rows):
        chars = []
        for c in range(COLS):
            v = 255 * (px[c, r] / 255) ** GAMMA
            chars.append(RAMP[round((255 - v) / 255 * (len(RAMP) - 1))])
        lines.append("".join(chars).rstrip())

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
        for r, line in enumerate(lines):
            if not line:
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
        f'font-size="{FONT_SIZE}" fill="{INK}">'
    )
    for r, line in enumerate(lines):
        if not line:
            continue
        clip = "" if static else f' clip-path="url(#c{r})"'
        # textLength pins the advance width so the grid stays aligned in any font.
        svg.append(
            f'<text x="{PAD}" y="{PAD + (r + 1) * CH - 2.5}" xml:space="preserve" '
            f'textLength="{len(line) * CW:.1f}" lengthAdjust="spacingAndGlyphs"{clip}>{esc(line)}</text>'
        )
    svg.append("</g>")

    if not static:
        for r, line in enumerate(lines):
            if not line:
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
