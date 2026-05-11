# Setup Guide

## One-time Setup

### 1. Create the GitHub repo

```
Repository name: yt-digest
Visibility: Public   ← GitHub Pages is free only for public repos
```

### 2. Push this folder to the repo

```bash
cd yt-digest
uv sync          # creates uv.lock and installs deps
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/dhilu0001/yt-digest.git
git branch -M main
git push -u origin main
```

### 3. Enable GitHub Pages

Go to: **Settings → Pages → Source → Deploy from a branch**
- Branch: `main`
- Folder: `/docs`

Your site will be at: `https://dhilu0001.github.io/yt-digest`

### 4. Add GitHub Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `YOUTUBE_API_KEY` | Your Google Cloud Console API key |
| `GEMINI_API_KEY` | Your Google AI Studio API key |
| `SITE_PASSWORD_HASH` | SHA-256 hash of your chosen password (see below) |

**To get your password hash:**
1. Open `https://dhilu0001.github.io/yt-digest/generate-hash.html` after deploying
2. Type your password and copy the hash
3. Paste it as `SITE_PASSWORD_HASH`

### 5. Enable YouTube Data API

Go to: [console.cloud.google.com](https://console.cloud.google.com)
- APIs & Services → Library → Search "YouTube Data API v3" → Enable

### 6. Run the first digest manually

Go to: **Actions → YT Digest → Run workflow**

This will fetch and summarize the latest videos and push them to your site.

---

## Adding More Channels

Go to: **Settings → Variables → Actions → New repository variable**
- Name: `CHANNELS`
- Value: `@NateBJones, @AnotherChannel, @YetAnother`

The workflow picks this up on the next run.

---

## How It Runs

- Automatically every day at 6 AM UTC
- Also runs on-demand via **Actions → YT Digest → Run workflow**
- Each run processes up to 5 new videos per channel
- Already-processed videos are skipped (tracked in `docs/data/index.json`)
