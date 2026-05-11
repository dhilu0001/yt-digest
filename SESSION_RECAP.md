# YT Digest — Session Recap (May 9, 2026)

## What We Built This Session

### 3-Column VS Code-Style Layout
Rebuilt the entire UI from a 2-column card grid into a VS Code / Linear-style 3-panel shell:

| Column | Width | Purpose |
|---|---|---|
| Icon Rail | 56px | Custom "YD" logo (3-line condensing icon — not YouTube logo) |
| Channel Rail | 220px | Channel list with video counts + Monthly Digests section |
| Main Panel | flex: 1 | Search + filters + card list + reading pane |

### Outlook-Style Reading Pane
- Clicking a card slides a reading pane in from the right (no modal overlay)
- Reading pane: **72% of main panel width** — dominant, like Outlook
- Card list compresses to 28%, drops thumbnails, becomes a compact list
- Selected card gets a red border (active state)

### Two-Level Sidebar Collapse
- `«` button (left of search bar): collapses both icon rail + channel rail → main panel goes full width
- `‹` button (top-left of reading pane): collapses the card list → reading pane goes 100%
- `✕` button: closes reading pane and resets both collapses
- Combine both collapses for full distraction-free reading

### Custom Icon
Replaced the YouTube play-triangle (copyright risk) with a custom icon:
3 condensing horizontal lines (long → medium → short) representing "digest = summarize content down".

### Monthly Digest System
**Script:** `scripts/generate_monthly_summaries.py`
- Groups all processed videos by `published_at[:7]` (year-month)
- Calls LLM with all that month's summaries combined
- Outputs: key themes, major developments, must-read picks, key takeaways
- Saves `docs/data/monthly/YYYY-MM.json` + `docs/data/monthly/index.json`
- Incremental — skips months already generated

**UI:** Monthly Digests section added to channel sidebar. Clicking a month loads the digest in the reading pane. Must-read picks link to the full video.

---

## Current State

### Data
- **46 videos** in `docs/data/index.json` (April–May 2026)
- **Backfill is currently running** in the background:
  - From: May 22, 2024 (channel start date)
  - Fetching: all videos not yet in `processed_ids`
  - Expected: ~200–400 videos, ~1–3 hours, ~$0.50–$1.50 (GPT-4o-mini)

### .env Settings (current)
```
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
MAX_VIDEOS_PER_RUN=500
BACKFILL_SINCE=2024-05-22T00:00:00Z
CHANNELS=@NateBJones
```

### Password
- Local test password: `digest123`
- To change: open `http://localhost:8080/generate-hash.html`, enter new password, copy hash, update `docs/config.json`

---

## What To Do Next Session

### 1. After Backfill Finishes — Generate Monthly Summaries
```powershell
cd yt-digest
uv run --env-file .env python scripts/generate_monthly_summaries.py
```
This generates May 2024 → April 2026 monthly digests. Takes ~30–60 min.

### 2. Reset .env for Daily Runs
After backfill and monthly generation are done, reset to daily-run settings:
```
MAX_VIDEOS_PER_RUN=20
# Remove BACKFILL_SINCE or leave it (harmless without BACKFILL=true)
```

### 3. Deploy to GitHub Pages
- Push the repo to GitHub
- Enable Pages: Settings → Pages → Branch: main, Folder: /docs
- Add GitHub Actions workflow for daily automation (already planned in SETUP.md)
- Add Secrets: YOUTUBE_API_KEY, OPENAI_API_KEY, SITE_PASSWORD_HASH

### 4. To Run the Backfill Manually (if needed)
```powershell
$env:BACKFILL = "true"; uv run --env-file .env python scripts/fetch_and_summarize.py
```

---

## Files Changed This Session

| File | What Changed |
|---|---|
| `docs/index.html` | Full rewrite: 3-column shell, custom icon, sidebar toggle, list-toggle, monthly section |
| `docs/styles.css` | Full rewrite: shell layout, icon/channel rails, reading pane, collapse states, monthly styles |
| `docs/app.js` | Full rewrite: channel sidebar, monthly digests, reading pane open/close, collapse toggles |
| `scripts/generate_monthly_summaries.py` | **New file** — generates monthly LLM digests |
| `docs/config.json` | Password temporarily reset to `digest123` (SHA-256 hash) |
| `.env` | Added MAX_VIDEOS_PER_RUN=500, BACKFILL_SINCE, removed BACKFILL=true |

---

## YouTube API Quota Reference
- **Free tier:** 10,000 units/day
- `search.list`: 100 units (daily runs use this)
- `playlistItems.list`: 1 unit (backfill uses this — very cheap)
- `videos.list`: 1 unit per video
- **Daily run (1 channel):** ~102 units — 1% of quota
- **Full backfill (400 videos):** ~410 units — safe within daily limit
