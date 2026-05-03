"""Collect GitHub repo traffic for all public repos owned by the user.
Appends new rows to data/*.csv. Idempotent — duplicate days are de-duped.

Env vars:
  GH_PAT   personal access token, scope: repo
  GH_USER  GitHub username (default: Darkaiser2)
"""
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

USER = os.environ.get("GH_USER", "Darkaiser2")
TOKEN = os.environ["GH_PAT"]
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "gh-traffic-logger",
}


def get(path: str, params: dict | None = None) -> dict | list:
    r = requests.get(f"{API}{path}", headers=HEADERS, params=params, timeout=30)
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return r.json()


def list_repos() -> list[dict]:
    """Authenticated endpoint returns public + private repos owned by the token user."""
    repos: list[dict] = []
    page = 1
    while True:
        batch = get("/user/repos", {"per_page": 100, "page": page, "affiliation": "owner"})
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork") and r.get("owner", {}).get("login") == USER]


def upsert_csv(path: Path, header: list[str], rows: list[list], key_idx: tuple[int, ...]):
    """Append rows; de-dupe by composite key columns."""
    existing: dict[tuple, list] = {}
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            file_header = next(reader, None)
            if file_header == header:
                for row in reader:
                    if len(row) >= len(header):
                        existing[tuple(row[i] for i in key_idx)] = row
    for row in rows:
        existing[tuple(row[i] for i in key_idx)] = row
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in sorted(existing.values()):
            w.writerow(row)


def collect_views_clones(repo_full: str, kind: str) -> list[list]:
    data = get(f"/repos/{repo_full}/traffic/{kind}")
    rows = []
    for item in data.get(kind, []):
        rows.append([item["timestamp"][:10], repo_full, item["count"], item["uniques"]])
    return rows


def collect_referrers(repo_full: str, today: str) -> list[list]:
    data = get(f"/repos/{repo_full}/traffic/popular/referrers") or []
    return [[today, repo_full, x["referrer"], x["count"], x["uniques"]] for x in data]


def collect_paths(repo_full: str, today: str) -> list[list]:
    data = get(f"/repos/{repo_full}/traffic/popular/paths") or []
    return [[today, repo_full, x["path"], x["title"][:80], x["count"], x["uniques"]] for x in data]


def main():
    repos = list_repos()
    print(f"[collect] {len(repos)} owned non-fork repos for {USER}")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    views, clones, refs, paths = [], [], [], []
    for r in repos:
        full = r["full_name"]
        try:
            views.extend(collect_views_clones(full, "views"))
            clones.extend(collect_views_clones(full, "clones"))
            refs.extend(collect_referrers(full, today))
            paths.extend(collect_paths(full, today))
            print(f"[collect] {full} ok")
        except requests.HTTPError as e:
            print(f"[collect] {full} skipped ({e.response.status_code})", file=sys.stderr)

    upsert_csv(DATA / "views.csv", ["date", "repo", "views", "uniques"], views, (0, 1))
    upsert_csv(DATA / "clones.csv", ["date", "repo", "clones", "uniques"], clones, (0, 1))
    upsert_csv(DATA / "referrers.csv", ["snapshot_date", "repo", "referrer", "count", "uniques"], refs, (0, 1, 2))
    upsert_csv(DATA / "paths.csv", ["snapshot_date", "repo", "path", "title", "count", "uniques"], paths, (0, 1, 2))
    print("[collect] csv updated")


if __name__ == "__main__":
    main()
