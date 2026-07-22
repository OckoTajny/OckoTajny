#!/usr/bin/env python3
"""Hand-author the neofetch-style info card SVG.

The heatmap already covers GitHub stats, so this card is for the story the
numbers can't tell: role, stack, the rice. Each line fades and slides in on a
short stagger (CSS keyframes inside the SVG – GitHub plays them in <img>),
prints once, then stays.

    python scripts/make_info_card.py            # writes info-card.svg
    STATIC=1 python scripts/make_info_card.py   # frozen frame for previews
"""

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "info-card.svg"

BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
INK = "#c9d1d9"
DIM = "#8b949e"
GREEN = "#3fb950"
BLUE = "#58a6ff"
CYAN = "#76e3ea"

# (key, value) – key rendered in green, value in ink. None = separator rule.
LINES = [
    ("jachym@arch", None),
    (None, None),
    ("OS", "Arch Linux x86_64"),
    ("WM", "Hyprland (Wayland)"),
    ("Role", "Full-Stack Developer @ djt-group"),
    ("Location", "Czech Republic"),
    ("Now", "Scalable, high-performance web apps"),
    ("Stack", "TypeScript · React · Next.js · Node.js"),
    ("Also", "Python · Prisma · PostgreSQL · Supabase"),
    ("Rice", "Hyprland dotfiles → OckoTajny/dotfiles"),
    ("Web", "jachym.djt-group.com"),
    ("Mail", "jachym@djt-group.com"),
]

PALETTE = ["#484f58", "#ff7b72", "#3fb950", "#d29922",
           "#58a6ff", "#bc8cff", "#76e3ea", "#c9d1d9"]

W = 560
FONT = 14
LH = 23
PAD = 22
BAR_H = 34
KEY_W = 96  # value column offset


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    n = len(LINES) + 1  # + palette row
    height = BAR_H + PAD + n * LH + PAD

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" aria-label="Jáchym Šolta – neofetch info card">'
    )

    if not static:
        svg.append(
            "<style>"
            ".ln{opacity:0;animation:in .45s ease-out both}"
            "@keyframes in{from{opacity:0;transform:translateX(-10px)}"
            "to{opacity:1;transform:none}}"
            "</style>"
        )

    svg.append(
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1}" rx="12" '
        f'fill="{BG}" stroke="{BORDER}"/>'
    )
    # Terminal title bar with traffic lights.
    svg.append(f'<path d="M0.5 12 a12 12 0 0 1 12 -11.5 h{W - 25} a12 12 0 0 1 12 11.5 v{BAR_H - 12} h-{W - 1} z" fill="{BAR}"/>')
    svg.append(f'<line x1="0.5" y1="{BAR_H}.5" x2="{W - 0.5}" y2="{BAR_H}.5" stroke="{BORDER}"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        svg.append(f'<circle cx="{20 + i * 20}" cy="{BAR_H / 2}" r="5.5" fill="{c}"/>')
    svg.append(
        f'<text x="{W / 2}" y="{BAR_H / 2 + 4}" text-anchor="middle" fill="{DIM}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12">'
        f"jachym@arch: ~/neofetch</text>"
    )

    svg.append(
        f'<g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{FONT}">'
    )

    def anim(i: int) -> str:
        return "" if static else f' class="ln" style="animation-delay:{0.35 + i * 0.13:.2f}s"'

    y0 = BAR_H + PAD + FONT
    for i, (key, val) in enumerate(LINES):
        y = y0 + i * LH
        if key is None:  # separator under the user@host header
            svg.append(
                f'<g{anim(i)}><line x1="{PAD}" y1="{y - 4}" x2="{PAD + 96}" y2="{y - 4}" '
                f'stroke="{DIM}" stroke-dasharray="2 2"/></g>'
            )
        elif val is None:  # user@host header
            svg.append(
                f'<g{anim(i)}><text x="{PAD}" y="{y}" fill="{CYAN}" font-weight="bold">'
                f'<tspan fill="{GREEN}">jachym</tspan><tspan fill="{DIM}">@</tspan>'
                f'<tspan fill="{BLUE}">arch</tspan></text></g>'
            )
        else:
            svg.append(
                f'<g{anim(i)}><text x="{PAD}" y="{y}" fill="{GREEN}" font-weight="bold">{esc(key)}:</text>'
                f'<text x="{PAD + KEY_W}" y="{y}" fill="{INK}">{esc(val)}</text></g>'
            )

    # Classic neofetch palette row.
    py = y0 + len(LINES) * LH - 10
    sw = 22
    blocks = "".join(
        f'<rect x="{PAD + i * sw}" y="{py}" width="{sw}" height="12" fill="{c}"/>'
        for i, c in enumerate(PALETTE)
    )
    svg.append(f"<g{anim(len(LINES))}>{blocks}</g>")

    svg.append("</g></svg>")
    OUT.write_text("\n".join(svg), encoding="utf-8")
    print(f"wrote {OUT} ({W}x{height}px)")


if __name__ == "__main__":
    main()
