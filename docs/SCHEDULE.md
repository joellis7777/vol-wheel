# On-time scans with cron-job.org (≈10 minutes, free)

GitHub's own cron runs this repo's scans hours late (since 2026-10-06 the 10:30 ET scan has never
run in its slot; the post-close scan starts around 21:00 ET). cron-job.org calls GitHub's "run
workflow" button for you, on time to the minute. GitHub's crons stay as a backup: a late run either
skips itself or harmlessly repeats a scan (alerts are deduplicated).

## Part A — a GitHub token that can only start this repo's scans

1. On github.com, click your avatar (top right) → **Settings**.
2. Left sidebar, at the bottom: **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens** → **Generate new token**.
3. Fill in:
   - **Token name:** `vol-wheel scheduler`
   - **Expiration:** pick a date up to a year out, and put a reminder in your calendar a week before
     it (when it expires the scans silently fall back to GitHub's late crons).
   - **Repository access:** **Only select repositories** → choose `joellis7777/vol-wheel`.
   - **Permissions → Repository permissions → Actions:** set to **Read and write**.
     (GitHub adds **Metadata: Read-only** by itself. Leave everything else at "No access".)
4. **Generate token**, then copy it right away (it starts with `github_pat_` and is shown once).
   Keep it somewhere private. It can only start or cancel this repo's workflow runs.

## Part B — the intraday job on cron-job.org

1. Go to **cron-job.org** → **Sign up** (free) → confirm your email → log in to the **Console**.
2. Optional but easiest: **Settings** (account) → **Time zone: America/New_York** → save. New jobs
   then default to Eastern time, and daylight saving is handled for you.
3. **Cronjobs** → **Create cronjob**. On the first tab (**Common**):
   - **Title:** `vol-wheel intraday`
   - **URL:**
     `https://api.github.com/repos/joellis7777/vol-wheel/actions/workflows/scan.yml/dispatches`
   - **Execution schedule:** choose **Custom** (user-defined), then select:
     - **Days of week:** Monday–Friday
     - **Hours:** 10, 11, 12, 13, 14, 15
     - **Minutes:** 0, 15, 30, 45
     - Plus one at the open: clone this job as `vol-wheel open` with **Hour 9, Minute 45** only.
       Why 9:45 and not 9:30: CBOE's quotes are delayed ~15 minutes, so a 9:30 scan still sees the
       pre-open book, and option spreads are widest in the first minutes. 9:45 ET (6:45 PT) is the
       first scan with real opening quotes.
     - **Days of month / Months:** every
   - If a **Time zone** field shows here, set it to **America/New_York**.
4. Switch to the **Advanced** tab:
   - **Request method:** **POST**
   - **Headers** — add these four (click "Add" for each; key on the left, value on the right):

     | Key | Value |
     |---|---|
     | `Accept` | `application/vnd.github+json` |
     | `Authorization` | `Bearer github_pat_…` (paste your token after `Bearer `) |
     | `X-GitHub-Api-Version` | `2022-11-28` |
     | `Content-Type` | `application/json` |

   - **Request body:**
     ```
     {"ref":"main","inputs":{"mode":"intraday","alerts":"true"}}
     ```
5. **Notifications** tab (optional): turn on "notify me when an execution fails".
6. **Test run** (button at the top of the job editor). Expect **HTTP 204** (an empty response is
   success). Then **Create** / **Save**.
   - 401 or 403 → the token or its Actions permission is wrong.
   - 404 → a typo in the URL, or the token wasn't given access to `vol-wheel`.
   - 422 → a typo in the body (it must be exactly the JSON above).

## Part C — the post-close job

Back on the Cronjobs list, use **Clone** on `vol-wheel intraday` (or create a new one the same way)
and change only:

- **Title:** `vol-wheel close`
- **Execution schedule → Custom:** Monday–Friday, **Hour 16**, **Minute 40**
- **Request body:**
  ```
  {"ref":"main","inputs":{"mode":"close","alerts":"true"}}
  ```

Test run (204), save.

## Part D — the extended-hours watch (pre-market and after hours)

Options only trade 09:30–16:00 ET, but shares trade before and after (limit orders). This job checks
each name's extended-hours price against the regular close and alerts on a big move (≥ 3% and ≥ 2σ)
with context: earnings and the implied move, the market moving with it, a swing low crossed. It is
price-only (about 20 small quotes, ~30 s) and writes `docs/data/extended.json` for the dashboard's
"After hours" / "Pre-market" panel; it never touches the option scan or the IV history.

Clone `vol-wheel intraday` again and change:

- **Title:** `vol-wheel extended`
- **Execution schedule → Custom:** Monday–Friday, **Hours 8, 9, 16**, **Minutes 0, 15, 30, 45**
  (the scan only works 08:30–09:30 and 16:00–17:00 ET, `extended_hours.windows`; the 8:00, 8:15,
  9:30 and 9:45 runs exit straight away)
- **Request body:**
  ```
  {"ref":"main","inputs":{"mode":"extended","alerts":"true"}}
  ```

Test run (204), save. Expect an "AFTER HOURS −8.0% · GOOG"-style alert at most once per name per
session, again only if the move deepens by another 3 points.

## Part E — check it worked

- GitHub → `vol-wheel` → **Actions**: each half hour a `scan` run appears with the event
  **workflow_dispatch**, finishing in about a minute.
- The dashboard header shows **Intraday HH:MM ET** with the latest half-hour.
- After 16:40 ET the header says **Post-close**, and the WATCH digest (if any names qualify)
  arrives on your phone a minute later.

## Notes

- Quotes are CBOE's free delayed feed (~15 min), so a 30-minute cadence catches a big move within
  roughly 15–45 minutes. Every 15 minutes also works (Minutes: 0, 15, 30, 45); GitHub Actions minutes
  are free for public repos.
- Market holidays: the jobs still fire; the scan sees no new prices and alerts don't repeat. You can
  pause the jobs on those days if you prefer.
- Renewing the token: generate a new one (same settings), then paste it into the `Authorization`
  header of both jobs.
