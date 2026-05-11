"""
Save a video's transcript + metadata to test_data/ for offline prompt iteration.
Usage: uv run --env-file .env python scripts/save_test_data.py <video_id>
"""
import os
import sys
import json
import re
from pathlib import Path
import googleapiclient.discovery
from youtube_transcript_api import YouTubeTranscriptApi

YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
TEST_DATA_DIR = Path("test_data")

youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
_ytt = YouTubeTranscriptApi()


def _parse_duration(iso: str) -> str:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mn, s = m.group(1), m.group(2), m.group(3)
    parts = ([f"{h}h"] if h else []) + ([f"{mn}m"] if mn else []) + ([f"{s}s"] if s else [])
    return " ".join(parts) or "0s"


def save_video(video_id: str):
    print(f"Fetching metadata for {video_id}...")
    resp = youtube.videos().list(part="snippet,contentDetails,statistics", id=video_id).execute()
    item = resp["items"][0]
    snippet = item["snippet"]
    cd = item["contentDetails"]
    stats = item["statistics"]

    transcript = None
    print("Fetching transcript...")
    try:
        fetched = _ytt.fetch(video_id, languages=["en"])
        transcript = " ".join(s.text for s in fetched)
        print(f"  Transcript: {len(transcript)} chars")
    except Exception as e:
        print(f"  No transcript: {e}")

    data = {
        "video_id": video_id,
        "title": snippet["title"],
        "channel_title": snippet["channelTitle"],
        "published_at": snippet["publishedAt"],
        "description": snippet["description"],
        "duration": _parse_duration(cd["duration"]),
        "view_count": stats.get("viewCount", "0"),
        "like_count": stats.get("likeCount", "0"),
        "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "transcript": transcript,
    }

    TEST_DATA_DIR.mkdir(exist_ok=True)
    out = TEST_DATA_DIR / f"{video_id}.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {out}")
    return data


if __name__ == "__main__":
    video_id = sys.argv[1] if len(sys.argv) > 1 else "W79FW7iUkro"
    save_video(video_id)
