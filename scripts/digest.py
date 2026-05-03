"""Send a Telegram digest of the last 7 days of GitHub traffic."""
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def window(rows: list[dict], days: int, date_col: str = "date") -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [r for r in rows if r.get(date_col, "") >= cutoff]


def sum_per_repo(rows: list[dict], col: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        try:
            out[r["repo"]] += int(r[col])
        except (KeyError, ValueError):
            pass
    return out


def main():
    views = load_rows(DATA / "views.csv")
    clones = load_rows(DATA / "clones.csv")
    refs = load_rows(DATA / "referrers.csv")

    last7 = sum_per_repo(window(views, 7), "views")
    prev7 = sum_per_repo(
        [r for r in views if (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d") <= r["date"] < (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")],
        "views",
    )
    clone7 = sum_per_repo(window(clones, 7), "clones")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_refs = [r for r in refs if r.get("snapshot_date") == today]
    top_ref_by_repo: dict[str, str] = {}
    for r in today_refs:
        repo = r["repo"]
        if repo not in top_ref_by_repo:
            top_ref_by_repo[repo] = f"{r['referrer']} ({r['count']})"

    total_now = sum(last7.values())
    total_prev = sum(prev7.values()) or 1
    delta = (total_now - total_prev) / total_prev * 100

    lines = [f"📊 *GitHub Traffic — {today}*", ""]
    for repo in sorted(last7, key=lambda k: -last7[k]):
        v = last7[repo]
        c = clone7.get(repo, 0)
        ref = top_ref_by_repo.get(repo, "-")
        short = repo.split("/", 1)[-1]
        lines.append(f"`{short[:28]:<28}` {v:>4}v {c:>2}c · {ref}")
    if not last7:
        lines.append("_no traffic in last 7 days_")
    lines += ["", f"*7d total:* {total_now} views ({delta:+.0f}% vs prev week)"]
    text = "\n".join(lines)

    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
        timeout=15,
    )
    r.raise_for_status()
    print("[digest] sent")


if __name__ == "__main__":
    main()
