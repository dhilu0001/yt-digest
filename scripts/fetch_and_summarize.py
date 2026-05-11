import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import googleapiclient.discovery
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
CHANNELS_ENV = os.environ.get("CHANNELS", "@NateBJones")
MAX_VIDEOS_PER_RUN = int(os.environ.get("MAX_VIDEOS_PER_RUN", "5"))

# LLM provider: "claude" (recommended), "gemini", "groq", or "openai"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

DOCS_DATA_DIR = Path("docs/data")
INDEX_FILE = DOCS_DATA_DIR / "index.json"

youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Lazy-init LLM clients
_gemini_client = None
_groq_client = None
_openai_client = None
_claude_client = None


def _llm_complete(prompt: str) -> str:
    global _gemini_client, _groq_client, _openai_client, _claude_client
    if LLM_PROVIDER == "claude":
        if not _claude_client:
            import anthropic
            _claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text or ""
    elif LLM_PROVIDER == "groq":
        if not _groq_client:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        resp = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
    elif LLM_PROVIDER == "openai":
        if not _openai_client:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=OPENAI_API_KEY)
        resp = _openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""
    else:  # gemini (default)
        if not _gemini_client:
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        resp = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=32768),
        )
        text = resp.text or ""
        if not text and resp.candidates:
            parts = resp.candidates[0].content.parts if resp.candidates[0].content else []
            text = "".join(getattr(p, "text", "") or "" for p in parts)
        return text


def resolve_channel(handle: str) -> tuple[str, str]:
    handle = handle.lstrip("@")
    resp = youtube.channels().list(part="id,snippet", forHandle=handle).execute()
    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: @{handle}")
    return items[0]["id"], items[0]["snippet"]["title"]


def _get_uploads_playlist(channel_id: str) -> str:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_latest_videos(channel_id: str, max_results: int = 10) -> list[dict]:
    """Fetch recent videos — used for daily cron runs."""
    resp = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_results,
    ).execute()
    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
            "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
            "description": item["snippet"]["description"],
        }
        for item in resp.get("items", [])
    ]


def fetch_all_videos_since(channel_id: str, since_date: str) -> list[dict]:
    """Fetch ALL videos published on or after since_date (ISO 8601).
    Used for initial backfill. Paginates through the full uploads playlist."""
    playlist_id = _get_uploads_playlist(channel_id)
    videos = []
    page_token = None

    while True:
        kwargs = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = youtube.playlistItems().list(**kwargs).execute()

        for item in resp.get("items", []):
            snippet = item["snippet"]
            published = snippet["publishedAt"]
            if published < since_date:
                return videos  # playlist is in reverse-chronological order
            resource = snippet.get("resourceId", {})
            if resource.get("kind") != "youtube#video":
                continue
            videos.append({
                "video_id": resource["videoId"],
                "title": snippet["title"],
                "published_at": published,
                "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                "description": snippet.get("description", ""),
            })

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return videos


def get_video_details(video_id: str) -> dict:
    resp = youtube.videos().list(part="contentDetails,statistics", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        return {}
    cd = items[0]["contentDetails"]
    stats = items[0]["statistics"]
    return {
        "duration": _parse_duration(cd["duration"]),
        "view_count": stats.get("viewCount", "0"),
        "like_count": stats.get("likeCount", "0"),
    }


def _parse_duration(iso: str) -> str:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mn, s = m.group(1), m.group(2), m.group(3)
    parts = ([f"{h}h"] if h else []) + ([f"{mn}m"] if mn else []) + ([f"{s}s"] if s else [])
    return " ".join(parts) or "0s"


_ytt = YouTubeTranscriptApi()


def get_transcript(video_id: str) -> str | None:
    try:
        fetched = _ytt.fetch(video_id, languages=["en"])
        return " ".join(s.text for s in fetched)
    except Exception:
        return None


def _extract_description_links(description: str) -> list[dict]:
    """Pull URLs from the video description — free alternative to Search grounding."""
    urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', description)
    seen = set()
    refs = []
    for url in urls:
        url = url.rstrip(".,;")
        if url in seen or "youtube.com" in url or "youtu.be" in url:
            continue
        seen.add(url)
        refs.append({"url": url, "title": url, "why_relevant": ""})
    return refs[:5]


def summarize(title: str, description: str, transcript: str | None, channel_title: str) -> dict:
    content = (transcript or description or title)[:30000]
    source_note = "full video transcript" if transcript else "video description (no transcript available)"

    prompt = f"""You are Ramu, a strict but warm teacher preparing complete beginners for their first AI career.

Your students are smart but new. They must compete with experienced practitioners, so you CANNOT skip or water down any detail. Your job: preserve every fact from the video AND make each one stick in memory using plain English + vivid analogies.

Video: "{title}" by {channel_title}
Source: {source_note}
Content: {content}

THE GOLDEN RULE: SPECIFIC + VIVID. Not "AI found vulnerabilities" but "[Specific tool from THIS video] found [specific number from THIS video] vulnerabilities in [specific software from THIS video] — that's like [concrete real-world analogy]." Always anchor your examples in facts from THIS video's content only.

BULLET RULES (strictly follow these):
- Generate AT LEAST 12 distinct bullets. Each bullet covers exactly ONE concept or argument. Do NOT merge two separate points into one bullet.
- Every bullet MUST contain at least one specific fact: a name, number, version, company, tool name, direct quote, or direct claim from the video.
- Lead with the FACT or CLAIM first. Do NOT start with a term name or label. Wrong: "Zero-day vulnerability: A dangerous bug..." Right: "The most dangerous type of bug is called a zero-day — meaning the software vendor has zero days of warning before attackers exploit it, so there is no patch available yet."
- Each bullet is 2-4 sentences: state the fact, explain why it matters, give an analogy.
- Analogies must be VIVID and CONCRETE — not "like a recipe" but "like baking a cake where you need specific flour — you cannot just swap in any white powder." Make the reader picture it.
- PRESERVE the speaker's exact quotes when memorable. Wrap them in double quotes: "A good human engineer wrote this" is becoming a much weaker security claim.
- If the speaker presents numbered options (e.g. "there are 3 ways to review code"), give each option its own mention within that bullet or as separate bullets. Do not collapse them into one vague sentence.
- Do NOT use markdown bold, italic, or headers inside bullet strings. Plain text only.
- Order by importance: most critical insight first.
- Never drop a detail because it seems too technical. Explain it instead.
- MUST-COVER: If the video mentions specific timelines ("4-5 months", "by end of year", "by Christmas"), percentages ("80% functional, 20% hygiene"), or cost/economic arguments ("implementation costs going to zero"), each MUST appear in its own bullet or be explicitly called out.

KEY TAKEAWAYS RULES:
- Write DO/ACTION items, not KNOW items. Wrong: "Understand the importance of code hygiene." Right: "Set a rule that at least 50% of your eval tests must check code hygiene (naming, structure, function length) — not just whether the code works. Most teams currently have this split backwards at 80/20."
- Each takeaway is 2-3 sentences: what to do, why, and what happens if you do not.
- At least one takeaway must address the immediate timeline the speaker states.

TECHNICAL TERMS RULES:
- Include 10 to 20 terms only. Pick the ones a beginner CANNOT skip: core tools, named systems, and jargon the speaker relies on most. Skip generic words any reader already knows.
- EVERY definition must end with an analogy starting with "Think of it like..." or "Like a...".
- Use plain English. No jargon in the definition itself.

IMPORTANT: Return ONLY valid JSON. No markdown fences, no extra text outside the JSON object. All strings must be plain text — no markdown inside JSON values.

{{
  "executive_summary": "2-3 sentences. The full story in plain English. Include specific names, numbers, and version numbers from the video.",
  "bullets": [
    "Fact-first sentence with specific name/number, then explanation, then vivid analogy. 2-4 sentences total.",
    "..."
  ],
  "key_takeaways": [
    "DO this specific action. Why it matters. What happens if you skip it. 2-3 sentences.",
    "..."
  ],
  "technical_terms": {{
    "ExactTermFromVideo": "Plain-English definition in 1-2 sentences. Think of it like [vivid concrete analogy]."
  }},
  "topics": ["3-5 topic tags"],
  "importance": "high if major release/finding/shift; medium if trend/analysis; low if opinion/commentary"
}}"""

    for attempt in range(4):
        try:
            text = _llm_complete(prompt).strip()
            if not text:
                raise ValueError(f"{LLM_PROVIDER} returned empty response")
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if "```" in text:
                    text = text[: text.rfind("```")]
            text = text.strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", text)
                if match:
                    return json.loads(match.group())
                raise
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                wait = 60 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s before retry {attempt + 1}/3")
                time.sleep(wait)
            else:
                raise


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8-sig"))
    return {"videos": [], "processed_ids": []}


def save_index(index: dict):
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    channels = [c.strip() for c in CHANNELS_ENV.split(",")]
    backfill = os.environ.get("BACKFILL", "").lower() == "true"
    backfill_since = os.environ.get("BACKFILL_SINCE", "2024-01-01T00:00:00Z")
    index = load_index()
    processed_ids = set(index.get("processed_ids", []))

    for handle in channels:
        print(f"\nChannel: {handle}")
        try:
            channel_id, channel_title = resolve_channel(handle)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if backfill:
            print(f"  BACKFILL MODE: fetching all videos since {backfill_since}")
            videos = fetch_all_videos_since(channel_id, since_date=backfill_since)
            print(f"  Found {len(videos)} total videos to consider")
        else:
            videos = fetch_latest_videos(channel_id, max_results=max(MAX_VIDEOS_PER_RUN, 50))
        new_count = 0

        for video in videos:
            vid_id = video["video_id"]
            if vid_id in processed_ids:
                continue
            if new_count >= MAX_VIDEOS_PER_RUN:
                print(f"  Reached limit of {MAX_VIDEOS_PER_RUN} new videos per run")
                break

            print(f"  Processing: {video['title'][:70]}")
            details = get_video_details(vid_id)
            transcript = get_transcript(vid_id)

            try:
                ai = summarize(video["title"], video["description"], transcript, channel_title)
            except Exception as e:
                print(f"  ERROR summarizing: {e}")
                continue

            desc_links = _extract_description_links(video["description"])

            entry = {
                "video_id": vid_id,
                "channel_handle": handle,
                "channel_title": channel_title,
                "title": video["title"],
                "published_at": video["published_at"],
                "thumbnail": video["thumbnail"],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "duration": details.get("duration", ""),
                "view_count": details.get("view_count", ""),
                "like_count": details.get("like_count", ""),
                "has_transcript": transcript is not None,
                **ai,
                "external_references": desc_links,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            out = DOCS_DATA_DIR / f"{vid_id}.json"
            out.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

            index["videos"].append({
                "video_id": vid_id,
                "title": video["title"],
                "channel_title": channel_title,
                "channel_handle": handle,
                "published_at": video["published_at"],
                "thumbnail": video["thumbnail"],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "duration": details.get("duration", ""),
                "topics": ai.get("topics", []),
                "importance": ai.get("importance", "medium"),
                "executive_summary": ai.get("executive_summary", ""),
                "bullet_count": len(ai.get("bullets", [])),
                "processed_at": entry["processed_at"],
            })
            processed_ids.add(vid_id)
            new_count += 1
            time.sleep(3)

    index["processed_ids"] = list(processed_ids)
    index["videos"].sort(key=lambda v: v["published_at"], reverse=True)
    save_index(index)
    print(f"\nDone. Total videos indexed: {len(index['videos'])}")


if __name__ == "__main__":
    main()
