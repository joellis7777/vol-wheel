# Reliable scan schedule (outside timer)

GitHub's own cron runs this repo's scans hours late: since 2026-10-06 the 10:30 ET scan has never
run in its slot and the post-close scan starts around 21:00 ET. An outside timer that calls GitHub's
"run workflow" API is on time to the minute. GitHub's crons stay in place as a backup: a late run
either skips itself or harmlessly repeats a scan (alerts are deduplicated).

## 1. Create a GitHub token that can only start this repo's workflows

GitHub → your avatar → **Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token**

- Token name: `vol-wheel scheduler`
- Expiration: up to 1 year (put a reminder in your calendar to renew it)
- Repository access: **Only select repositories → joellis7777/vol-wheel**
- Permissions → Repository permissions → **Actions: Read and write** (Metadata: Read is added
  automatically). Nothing else.

Copy the token (it starts with `github_pat_`). Anyone holding it can only start or cancel this
repo's workflow runs.

## 2. Create two jobs at cron-job.org (free account)

Both jobs use the same request:

- URL: `https://api.github.com/repos/joellis7777/vol-wheel/actions/workflows/scan.yml/dispatches`
- Advanced → Request method: **POST**
- Advanced → Headers:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer github_pat_…` (your token)
  - `X-GitHub-Api-Version: 2022-11-28`
  - `Content-Type: application/json`
- Time zone: **America/New_York** (cron-job.org then handles daylight saving)
- A successful call returns **HTTP 204** (no content). Enable "notify me on failure".

| Job | Schedule (ET, Mon–Fri) | Request body |
|---|---|---|
| vol-wheel intraday | every 30 min, 10:00–15:30 (minutes 0 and 30, hours 10–15) | `{"ref":"main","inputs":{"mode":"intraday","alerts":"true"}}` |
| vol-wheel close | 16:40 | `{"ref":"main","inputs":{"mode":"close","alerts":"true"}}` |

Quotes are CBOE's free delayed feed (~15 min), so a 30-minute cadence catches a big move within
roughly 15–45 minutes. Every 15 minutes also works; GitHub Actions minutes are free for public repos.

## 3. Check it

After the first scheduled call, the repo's Actions tab shows a `scan` run with event
`workflow_dispatch`, and the dashboard header shows "Intraday HH:MM ET".
