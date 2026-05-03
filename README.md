# gh-traffic-logger

Daily snapshot of GitHub repo traffic for all my public repos. Persists beyond GitHub's 14-day window and sends a Telegram digest each morning.

## What it does

- Runs daily at 12:00 UTC via GitHub Actions
- Calls `GET /repos/{owner}/{repo}/traffic/{views,clones,popular/referrers,popular/paths}` for every owned non-fork repo
- Appends results to `data/*.csv` (de-duped by date+repo so re-runs are safe)
- Sends a Markdown summary to Telegram covering last 7d vs prior 7d
- Commits the updated CSVs back to the repo for permanent history

## Output

| File | What |
|---|---|
| `data/views.csv` | one row per (date, repo) — total + unique views |
| `data/clones.csv` | one row per (date, repo) — clone count + unique cloners |
| `data/referrers.csv` | top referrers per repo, snapshotted daily |
| `data/paths.csv` | top page paths per repo, snapshotted daily |

## Setup

Required repo secrets (Settings → Secrets → Actions):

| Secret | Purpose |
|---|---|
| `GH_PAT` | personal access token, classic, scope `repo` (read traffic across all your repos) |
| `TELEGRAM_BOT_TOKEN` | bot token for digest delivery |
| `TELEGRAM_CHAT_ID` | chat ID to send digest to |

Optional repo variable: `GH_USER` (default `Darkaiser2`).

## Run locally

```powershell
$env:GH_PAT = "ghp_..."
$env:TELEGRAM_BOT_TOKEN = "..."
$env:TELEGRAM_CHAT_ID = "..."
python scripts/collect.py
python scripts/digest.py
```

## Manual trigger

Actions tab → `daily-traffic` → Run workflow.

## Cost

$0. Public repo = unlimited Actions minutes. ~10 GitHub API calls per repo per day, well under the 5000/hr authenticated limit.
