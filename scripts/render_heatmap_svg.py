#!/usr/bin/env python3
"""Render data/contributions.json as an animated 53-week heatmap SVG.

The classic calendar of rounded boxes on a GitHub-ish green ramp, revealed
once with a diagonal line-after-line slide-down (CSS keyframes that play on
load and freeze — no looping glow), plus a Less→More legend and a stats
footer. Output: contrib-heatmap.svg.

    python scripts/render_heatmap_svg.py
    STATIC=1 python scripts/render_heatmap_svg.py   # frozen frame
"""

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32",
           "#26a641", "#39d353", "#69f0a0"]
#          none -> brightest (level 5 is a neon top end for standout days)

CELL = 11
PITCH = 15  # cell + gap
PAD = 16
LABEL_W = 30   # Mon/Wed/Fri gutter
LABEL_H = 20   # month row
FOOTER_H = 34

BG = "#0d1117"
BORDER = "#30363d"
DIM = "#8b949e"
INK = "#c9d1d9"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    data = json.loads(SRC.read_text(encoding="utf-8"))
    days = data["days"]

    first = dt.date.fromisoformat(days[0]["date"])
    # Column 0 starts on the Sunday of the first day's week, like GitHub.
    origin = first - dt.timedelta(days=(first.weekday() + 1) % 7)

    best = data["best_day"]["count"]
    # Neon top end: only standout days get level 5, and only once the account
    # has real volume — otherwise stick to GitHub's own 0–4 levels.
    neon_min = max(15, round(best * 0.8)) if best >= 10 else None

    cells = []
    month_marks = {}  # week col -> month label
    weeks = 0
    for d in days:
        date = dt.date.fromisoformat(d["date"])
        col = (date - origin).days // 7
        row = (date.weekday() + 1) % 7
        weeks = max(weeks, col + 1)
        level = min(d["level"], 4)
        if neon_min and d["count"] >= neon_min:
            level = 5
        cells.append((col, row, level, d))
        if date.day <= 7 and row == 0 or (col not in month_marks and date.day == 1):
            month_marks.setdefault(col, MONTHS[date.month - 1])

    grid_w = weeks * PITCH - (PITCH - CELL)
    grid_h = 7 * PITCH - (PITCH - CELL)
    width = PAD + LABEL_W + grid_w + PAD
    height = PAD + LABEL_H + grid_h + FOOTER_H + PAD

    x0 = PAD + LABEL_W
    y0 = PAD + LABEL_H

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{data["total"]} GitHub contributions in the last year">'
    )
    if not static:
        # No opacity:0 on the classes themselves — renderers that ignore CSS
        # animations (GitHub mobile app, rsvg, embed thumbnailers) must still
        # see the finished graph. Animating browsers get the cascade via
        # fill-mode:both, which applies the from-frame during each delay.
        svg.append(
            "<style>"
            ".d{animation:drop .5s cubic-bezier(.2,.7,.3,1) both}"
            "@keyframes drop{from{opacity:0;transform:translateY(-8px)}"
            "to{opacity:1;transform:none}}"
            ".f{animation:fade .6s ease-out both}"
            "@keyframes fade{from{opacity:0}to{opacity:1}}"
            "</style>"
        )
    svg.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" '
        f'fill="{BG}" stroke="{BORDER}"/>'
    )

    font = 'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12"'

    # Month labels.
    prev = None
    for col, label in sorted(month_marks.items()):
        if label == prev:
            continue
        prev = label
        svg.append(
            f'<text x="{x0 + col * PITCH}" y="{PAD + 12}" fill="{DIM}" {font}>{label}</text>'
        )
    # Day labels.
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        svg.append(
            f'<text x="{PAD}" y="{y0 + row * PITCH + CELL - 2}" fill="{DIM}" {font}>{label}</text>'
        )

    # The grid. Diagonal reveal: delay grows with col + row.
    for col, row, level, d in cells:
        delay = "" if static else (
            f' class="d" style="animation-delay:{0.2 + (col + row) * 0.022:.3f}s"'
        )
        svg.append(
            f'<rect x="{x0 + col * PITCH}" y="{y0 + row * PITCH}" '
            f'width="{CELL}" height="{CELL}" rx="2.5" fill="{PALETTE[level]}"{delay}>'
            f'<title>{d["count"]} contributions on {d["date"]}</title></rect>'
        )

    late = "" if static else f' class="f" style="animation-delay:{0.2 + (weeks + 7) * 0.022 + 0.3:.2f}s"'

    # Stats footer.
    fy = y0 + grid_h + 22
    svg.append(
        f'<g{late}>'
        f'<text x="{x0}" y="{fy}" fill="{INK}" {font}>'
        f'<tspan fill="{PALETTE[4]}">{data["total"]:,}</tspan> contributions in the last year'
        f'<tspan fill="{DIM}">   ·   current streak {data["current_streak"]}d'
        f'   ·   longest {data["longest_streak"]}d'
        f'   ·   best day {data["best_day"]["count"]}</tspan></text></g>'
    )

    # Less -> More legend, bottom right.
    lx = width - PAD - 6 * (CELL + 3) - 70
    swatches = "".join(
        f'<rect x="{lx + 30 + i * (CELL + 3)}" y="{fy - CELL + 2}" width="{CELL}" '
        f'height="{CELL}" rx="2.5" fill="{c}"/>'
        for i, c in enumerate(PALETTE)
    )
    svg.append(
        f'<g{late}><text x="{lx}" y="{fy}" fill="{DIM}" {font}>Less</text>{swatches}'
        f'<text x="{lx + 30 + 6 * (CELL + 3) + 4}" y="{fy}" fill="{DIM}" {font}>More</text></g>'
    )

    svg.append("</svg>")
    OUT.write_text("\n".join(svg), encoding="utf-8")
    print(f"wrote {OUT} ({weeks} weeks, {width}x{height}px)")


if __name__ == "__main__":
    main()
