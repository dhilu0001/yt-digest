"""
Test the summarization prompt on a saved transcript without making YouTube API calls.
Edit the prompt in this file freely — no API credits wasted on YouTube.

Usage: uv run --env-file .env python scripts/test_prompt.py <video_id>
       uv run --env-file .env python scripts/test_prompt.py W79FW7iUkro
"""
import os
import sys
import json
from pathlib import Path
from google import genai

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
TEST_DATA_DIR = Path("test_data")


def build_prompt(title: str, channel_title: str, content: str) -> str:
    # ── EDIT THIS PROMPT TO ITERATE ──────────────────────────────────────────────
    return f"""You are Ramu, a teacher preparing students for their first AI career.

Your students are bright beginners starting their AI journey. They must compete with experienced practitioners — so you cannot skip any important detail. Your job is to keep ALL the specific facts from the video but explain them so a beginner can understand AND remember them.

Video: "{title}" by {channel_title}
Content: {content}

The golden rule: SPECIFIC + SIMPLE. Use only facts that come directly from THIS video's content. Not vague ("AI found vulnerabilities") but precise ("[tool from this video] found [number from this video] [specific finding from this video]").

Your teaching rules:
- KEEP every specific name, number, tool name, company, and finding from the video.
- EXPLAIN each one in plain English with a real-world analogy if helpful.
- Each bullet: one concept, fully explained. 1-3 sentences. Lead with the fact, then the analogy.
- Order by importance — most critical insight first.
- Technical terms: define them briefly in the same bullet where they first appear.
- Never drop a detail because it seems "too technical" — explain it instead.

Return ONLY valid JSON (no markdown fences):
{{
  "executive_summary": "2-3 sentences. The full story of what happened, in plain English. Include specific names and numbers.",
  "bullets": [
    "Specific fact from the video, explained simply. 1-3 sentences.",
    "..."
  ],
  "key_takeaways": [
    "What a student must KNOW or DO after this lesson. Specific, actionable. 4-6 items.",
    "..."
  ],
  "technical_terms": {{
    "ExactTermFromVideo": "Plain-English explanation + real-world analogy if helpful. 1-2 sentences."
  }},
  "topics": ["3-5 topic tags"],
  "importance": "high / medium / low"
}}"""
    # ──────────────────────────────────────────────────────────────────────────────


def run_test(video_id: str):
    test_file = TEST_DATA_DIR / f"{video_id}.json"
    if not test_file.exists():
        print(f"No test data for {video_id}. Run: uv run --env-file .env python scripts/save_test_data.py {video_id}")
        return

    data = json.loads(test_file.read_text(encoding="utf-8"))
    content = (data.get("transcript") or data.get("description") or data["title"])[:30000]
    title = data["title"]
    channel = data["channel_title"]

    print(f"Provider: {LLM_PROVIDER} | Model: {GROQ_MODEL if LLM_PROVIDER == 'groq' else GEMINI_MODEL}")
    print(f"Running prompt on: {title[:70]}")
    print(f"Content source: {'transcript' if data.get('transcript') else 'description'} ({len(content)} chars)")
    print("-" * 60)

    prompt = build_prompt(title, channel, content)

    if LLM_PROVIDER == "groq":
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3,
        )
        text = resp.choices[0].message.content or ""
    else:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = (resp.text or "").strip()

    print(text)
    print("\n" + "=" * 60)

    # Try to parse and pretty-print
    try:
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if "```" in text:
                text = text[: text.rfind("```")]
        parsed = json.loads(text.strip())
        print("\n[PARSED OK]")
        print("Executive summary:", parsed.get("executive_summary", "")[:200])
        print(f"Bullets: {len(parsed.get('bullets', []))}")
        print(f"Takeaways: {len(parsed.get('key_takeaways', []))}")
        print(f"Terms: {len(parsed.get('technical_terms', {}))}")
        print(f"Importance: {parsed.get('importance')}")
    except Exception as e:
        print(f"[PARSE ERROR] {e}")


if __name__ == "__main__":
    video_id = sys.argv[1] if len(sys.argv) > 1 else "W79FW7iUkro"
    run_test(video_id)
