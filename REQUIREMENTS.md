# YT Digest — Requirements

## Problem

Keeping up with the AI world via YouTube (specifically [@NateBJones](https://www.youtube.com/@NateBJones/videos)) is valuable but time-consuming. The user no longer has enough time to watch videos regularly.

## Goal

Build an automated YouTube digest tool that summarizes new videos from the channel, hosted on GitHub Pages — accessible to the user and their wife, with a path to future monetization.

## What We Have

| Resource | Detail |
|---|---|
| Google Cloud Console API key | For YouTube Data API v3 (fetching video metadata/transcripts) |
| Google AI Studio API key | For Gemini (AI summarization) |
| GitHub account | For hosting via GitHub Pages |
| Target channel | [https://www.youtube.com/@NateBJones/videos](https://www.youtube.com/@NateBJones/videos) |

## Core Requirements

1. **Auto-fetch** new videos — starting with NateBJones, but architecture must support adding other channels later
2. **AI-summarize** each video with:
   - All important points covered (nothing skipped)
   - Technical terms/tools/models highlighted
   - Video metadata (title, date, duration, URL) for reference
3. **Publish** summaries to a GitHub Pages site automatically
4. **Accessible** to at least two users (user + wife) without friction
5. **Monetization-ready** — architecture should allow adding a paywall or ads later
6. **Zero cost** — use only free tiers; no paid services

## Digest Entry Format (per video)

```
[Video Title] — [Channel] — [Date] — [Duration]
[YouTube URL]

## Summary
<comprehensive summary covering all key points>

## Technical Terms & Tools Mentioned
- Term 1: brief explanation
- Term 2: brief explanation

## Key Takeaways
- Bullet 1
- Bullet 2
- ...
```

## Automation Schedule

- **Daily GitHub Actions cron job** (runs every day, checks for new videos, publishes if any found)
- Costs $0 — within GitHub Actions free tier for public repos

## Hosting

- GitHub Pages (static site)
- GitHub Actions for automation (free)

## Out of Scope (for now)

- Mobile app
- User accounts / login system

## GitHub

- Username: `dhilu0001`
- Profile: https://github.com/dhilu0001
- Planned repo: `dhilu0001/yt-digest` (to be created)

## Site Access

- **Now:** Basic client-side password gate (keeps casual visitors out; not cryptographically secure)
- **Future:** Swap for a proper auth/paywall when monetizing

## Monetization

- Model TBD — architecture must allow adding ads or a subscription paywall without a full rewrite
- Suggested path: start public+password → add Google AdSense or a Stripe paywall later

## Open Questions

> None remaining — all decisions resolved. Ready to implement.
