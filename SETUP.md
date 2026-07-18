# Animated GitHub profile — how it works

This is the **profile repo** — the magic repo whose `README.md` renders on top
of the profile page at [github.com/OckoTajny](https://github.com/OckoTajny).
It was generated in `OckoTajny/jachym-portfolio` (branch
`claude/animated-github-profile-lzowyp`, folder `github-profile/`) and copied
here.

Built after [How I Built an Animated GitHub Profile README](https://avivashishta.com)
— ASCII portrait + neofetch card + live contribution graph, all animated SVG,
no JavaScript, no tokens, no third-party stats services.

## What's here

| File | What it is |
| --- | --- |
| `README.md` | The profile README — terminal layout placing the three SVGs |
| `jachym-ascii.svg` | Self-typing monochrome ASCII portrait (SMIL row-wipe + cursor) |
| `info-card.svg` | neofetch-style card — role, stack, rice (CSS line stagger) |
| `contrib-heatmap.svg` | 53-week contribution calendar, diagonal reveal + stats footer |
| `data/contributions.json` | Raw calendar days + derived streak/best-day stats |
| `source-prepped.png` | Intermediate: background-removed, CLAHE'd grayscale photo |
| `scripts/` | The five generators (see below) |
| `.github/workflows/update-profile-art.yml` | Daily cron that re-scrapes + re-renders the heatmap |

## Keeping it fresh

The **Update profile art** workflow re-scrapes the public contribution
calendar (no token) and re-renders `contrib-heatmap.svg` daily at ~06:17 UTC,
on every push to `main`, and on demand from the Actions tab
(`workflow_dispatch`). The initial `data/contributions.json` was seeded from
the portfolio repo's git history; the first workflow run replaced it with the
real calendar.

## Regenerating pieces

Daily deps are just `requests` + `beautifulsoup4` (`scripts/requirements.txt`).
The portrait toolchain is heavy and local-only
(`scripts/requirements-portrait.txt`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt

# Heatmap (what the cron does):
python scripts/fetch_contributions.py     # GITHUB_USER=... to override
python scripts/render_heatmap_svg.py

# Info card (edit LINES in the script):
python scripts/make_info_card.py

# Portrait (only when the photo changes):
pip install -r scripts/requirements-portrait.txt
python scripts/prep_photo.py photo.jpg --crop X Y W H   # rembg; --engine grabcut = offline fallback
python scripts/make_ascii_svg.py
```

`STATIC=1` before `make_ascii_svg.py`, `make_info_card.py` or
`render_heatmap_svg.py` emits a frozen final frame (handy for Quick Look —
some preview apps don't play SMIL/CSS animations).

## Why this works on GitHub

GitHub strips `<script>` and inline CSS from READMEs, but renders SVGs
embedded via `<img>` **and plays their SMIL + CSS-keyframe animations**. So
all motion lives inside the SVG files; the README just places them. Other
gotchas encoded in the layout: inline `style=` is stripped (only `<br>` gives
vertical space), `<h1>`/`<h2>` draw a full-width rule (use `<h3>`), and a
`<table>` is the only reliable way to put two images on one row.
