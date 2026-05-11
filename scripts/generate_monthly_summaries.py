"""
Generate monthly digest summaries from existing per-video JSON files.

Run after the backfill is complete. Only generates summaries for months
that don't already have one. Safe to re-run incrementally.

Usage: uv run --env-file .env python scripts/generate_monthly_summaries.py
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

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
MONTHLY_DIR = DOCS_DATA_DIR / "monthly"
INDEX_FILE = DOCS_DATA_DIR / "index.json"
MONTHLY_INDEX_FILE = MONTHLY_DIR / "index.json"

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
    else:
        if not _gemini_client:
            from google import genai
            from google.genai import types
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        from google.genai import types
        resp = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=8192),
        )
        return resp.text or ""


def month_label(ym: str) -> str:
    dt = datetime.strptime(ym, "%Y-%m")
    return dt.strftime("%B %Y")


def build_monthly_prompt(ym: str, videos: list[dict]) -> str:
    label = month_label(ym)
    lines = []
    for v in videos:
        lines.append(f"\n--- VIDEO_ID: {v['video_id']} | Title: {v['title']} ---")
        if v.get("executive_summary"):
            lines.append(f"Summary: {v['executive_summary']}")
        if v.get("bullets"):
            lines.append("Key points:")
            for b in v["bullets"][:6]:
                lines.append(f"  * {b}")
        if v.get("importance"):
            lines.append(f"Importance: {v['importance']}")
        if v.get("topics"):
            lines.append(f"Topics: {', '.join(v['topics'])}")

    content = "\n".join(lines)[:40000]

    return f"""You are Ramu, an AI education teacher synthesizing a monthly digest for students beginning their AI careers.

Month: {label}
Videos this month: {len(videos)}

Below are the summaries of all {len(videos)} videos published in {label}.
IMPORTANT: Each video block starts with "VIDEO_ID: <id>" — use that exact id string in must_reads.video_id.

{content}

Your job: synthesize these into a rich monthly digest that helps students understand:
1. What were the dominant themes of {label}? (identify 4-6 concrete recurring themes)
2. What were the biggest developments or announcements? (list at least 5-8 specific ones with names/numbers)
3. Which 3 videos are absolute must-reads and why? (use the exact VIDEO_ID from the block header)
4. What should a student DO differently after reading this month? (give 4-6 specific actionable takeaways)

Rules:
- Only use facts from the videos above. No external knowledge.
- Be specific: name the tools, models, companies, and numbers from the videos.
- The must-read picks must justify WHY that video is essential.
- Executive summary: 5-6 sentences covering the full arc of the month — name specific models, companies, and numbers.
- topics_breakdown counts must sum to approximately {len(videos)} (every video should belong to at least one topic).

Return ONLY valid JSON (no markdown fences):
{{
  "month": "{ym}",
  "label": "{label}",
  "video_count": {len(videos)},
  "executive_summary": "5-6 sentences summarizing the full arc of {label}. Name specific models, companies, tools, and numbers. Cover what was debated, what shipped, and what students should know.",
  "key_themes": [
    "Theme Name: 2-3 sentences on what specifically happened in this theme — name the tools, models, or companies involved.",
    "Theme Name: ...",
    "(4-6 themes total)"
  ],
  "major_developments": [
    "Name the specific tool/model/company + what happened + why it matters. 2 sentences.",
    "...",
    "(5-8 developments total)"
  ],
  "must_reads": [
    {{
      "video_id": "EXACT_VIDEO_ID_FROM_VIDEO_ID_FIELD_ABOVE",
      "title": "exact title from above",
      "why": "2-3 sentences: what makes this video essential, what specific insight it delivers, and what action a student should take after watching."
    }},
    {{...}},
    {{...}}
  ],
  "key_takeaways": [
    "Specific action a student should take. Start with a verb. Name a tool or skill. 2 sentences.",
    "...",
    "(4-6 takeaways total)"
  ],
  "topics_breakdown": {{
    "TopicName": count_of_videos_covering_this_topic
  }}
}}"""


def generate_monthly(ym: str, video_ids: list[str]) -> dict | None:
    videos = []
    for vid_id in video_ids:
        f = DOCS_DATA_DIR / f"{vid_id}.json"
        if f.exists():
            try:
                videos.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    if not videos:
        return None

    prompt = build_monthly_prompt(ym, videos)
    for attempt in range(3):
        try:
            text = _llm_complete(prompt).strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if "```" in text:
                    text = text[: text.rfind("```")]
            text = text.strip()
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                import re
                m = re.search(r"\{[\s\S]*\}", text)
                if m:
                    result = json.loads(m.group())
                else:
                    raise
            result["video_ids"] = video_ids
            result["generated_at"] = datetime.utcnow().isoformat() + "Z"
            return result
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 60 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"    ERROR: {e}")
                return None


def main():
    if not INDEX_FILE.exists():
        print("No index.json found. Run fetch_and_summarize.py first.")
        return

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8-sig"))
    videos = index.get("videos", [])

    # Group video IDs by month
    by_month: dict[str, list] = defaultdict(list)
    for v in videos:
        ym = v["published_at"][:7]
        by_month[ym].append(v["video_id"])

    months = sorted(by_month.keys())
    print(f"Found {len(months)} months spanning {months[0]} to {months[-1]}")

    # Load existing monthly index
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    if MONTHLY_INDEX_FILE.exists():
        monthly_index = json.loads(MONTHLY_INDEX_FILE.read_text(encoding="utf-8"))
    else:
        monthly_index = {"months": []}
    done_months = {m["month"] for m in monthly_index.get("months", [])}

    new_count = 0
    for ym in months:
        vid_ids = by_month[ym]
        if ym in done_months:
            print(f"  {ym}: already done ({len(vid_ids)} videos), skipping")
            continue

        print(f"  {ym}: generating digest for {len(vid_ids)} videos…")
        result = generate_monthly(ym, vid_ids)
        if not result:
            print(f"  {ym}: FAILED, skipping")
            continue

        out = MONTHLY_DIR / f"{ym}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        monthly_index["months"].append({
            "month": ym,
            "label": month_label(ym),
            "video_count": len(vid_ids),
            "executive_summary": result.get("executive_summary", ""),
            "key_themes": result.get("key_themes", [])[:3],
        })
        done_months.add(ym)
        new_count += 1
        print(f"  {ym}: done")
        time.sleep(2)

    monthly_index["months"].sort(key=lambda m: m["month"], reverse=True)
    MONTHLY_INDEX_FILE.write_text(
        json.dumps(monthly_index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nDone. Generated {new_count} new monthly digests. Total: {len(monthly_index['months'])}")


if __name__ == "__main__":
    main()
