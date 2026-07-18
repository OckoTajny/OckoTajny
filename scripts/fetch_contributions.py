#!/usr/bin/env python3
"""Fetch the real contribution calendar — no token, no GraphQL.

GitHub serves every user's contribution calendar as public HTML at
https://github.com/users/<username>/contributions — the same fragment the
profile page itself embeds. We fetch it with requests, parse the day cells
with BeautifulSoup, and write data/contributions.json with the raw days plus
derived stats (streaks, best day, monthly totals).

    python scripts/fetch_contributions.py            # default user
    GITHUB_USER=someone python scripts/fetch_contributions.py
"""

import datetime as dt
import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GITHUB_USER", "OckoTajny")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT = Path(__file__).resolve().parent.parent / "data" / "contributions.json"

COUNT_RE = re.compile(r"^([\d,]+|No)\s+contribution", re.IGNORECASE)


def parse_days(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Tooltip text ("3 contributions on July 4th.") lives in <tool-tip>
    # elements keyed to each cell's id via the `for` attribute.
    tips = {t.get("for"): t.get_text(strip=True) for t in soup.find_all("tool-tip")}

    days = []
    for td in soup.find_all("td", class_="ContributionCalendar-day"):
        date = td.get("data-date")
        if not date:
            continue
        count = 0
        m = COUNT_RE.match(tips.get(td.get("id"), ""))
        if m and m.group(1).lower() != "no":
            count = int(m.group(1).replace(",", ""))
        days.append({"date": date, "count": count, "level": int(td.get("data-level", 0))})

    if not days:
        raise SystemExit(
            "no ContributionCalendar-day cells found — GitHub may have changed "
            "the markup; inspect the fetched HTML and update parse_days()."
        )
    return sorted(days, key=lambda d: d["date"])


def derive_stats(days: list[dict]) -> dict:
    counts = {d["date"]: d["count"] for d in days}
    total = sum(counts.values())
    best = max(days, key=lambda d: d["count"])

    longest = current = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    # Current streak counts back from the last day; today being 0 doesn't
    # break a streak that's still alive from yesterday.
    dates = [dt.date.fromisoformat(d["date"]) for d in days]
    day = dates[-1]
    if counts[day.isoformat()] == 0:
        day -= dt.timedelta(days=1)
    while day.isoformat() in counts and counts[day.isoformat()] > 0:
        current += 1
        day -= dt.timedelta(days=1)

    monthly: dict[str, int] = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]

    return {
        "total": total,
        "best_day": {"date": best["date"], "count": best["count"]},
        "current_streak": current,
        "longest_streak": longest,
        "monthly": monthly,
    }


def main() -> None:
    resp = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (profile-art fetcher)"},
        timeout=30,
    )
    resp.raise_for_status()
    days = parse_days(resp.text)

    data = {
        "username": USERNAME,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        **derive_stats(days),
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {data['total']} contributions across {len(days)} days")


if __name__ == "__main__":
    main()
