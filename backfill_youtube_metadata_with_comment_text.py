"""
Backfill YouTube metadata for existing notes.json
-------------------------------------------------

Run from your research_tool folder:

    python3 backfill_youtube_metadata_with_comment_text.py

Requires:

    export YOUTUBE_API_KEY="your_key_here"

What it does:
- reads notes.json
- creates a timestamped backup before changing anything
- fetches missing YouTube API metadata for older notes
- saves updated notes.json
- stores counts:
    comments_scanned
    comments_ai_mentions
- also stores the text of comments that mention the AI keywords:
    ai_comment_texts

AI comment words counted are in AI_COMMENT_WORDS
"""

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
NOTES_PATH = BASE_DIR / "notes.json"
BACKUP_DIR = BASE_DIR / "backedup_notes"

COMMENT_SCAN_LIMIT = 15000 #big number, reduce if you need to save tokens
AI_COMMENT_WORDS = ["ai", "clanker", "slop", "chatgpt", "fake", "bot",
                    "sora", "nanobanana", "pika", "openai", "luma", "runway",
                    "kling", "llm", "copilot", "gemini", "anthropic", "claude",
                    "generated", "genAI", "synthetic", "deepfake", "glitch",
                    "skvip", "feik"]


def extract_video_id(url: str) -> str:
    if not url:
        return ""

    patterns = [
        r"v=([\w-]{11})",
        r"youtu\.be/([\w-]{11})",
        r"shorts/([\w-]{11})",
        r"embed/([\w-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return ""


def parse_iso8601_duration(duration: str) -> str:
    if not duration or not duration.startswith("PT"):
        return ""

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return ""

    hours, minutes, seconds = match.groups()
    h = int(hours) if hours else 0
    m = int(minutes) if minutes else 0
    s = int(seconds) if seconds else 0

    if h:
        return f"{h}:{m:02d}:{s:02d}"

    return f"{m}:{s:02d}"


def matched_ai_words(text: str) -> list:
    """Return AI-related keywords found in comment text."""
    if not text:
        return []

    lowered = text.lower()

    patterns = {
        "AI": r"\bai\b",
        "clanker": r"\bclanker\b",
        "slop": r"\bslop\b",
        "chatGPT": r"\bchatgpt\b",
        "fake": r"\bfake\b",
        "bot": r"\bbot\b",
    }

    return [
        word
        for word, pattern in patterns.items()
        if re.search(pattern, lowered)
    ]


def fetch_ai_comment_mentions(video_id: str, api_key: str, limit: int) -> dict:
    """Scan top-level comments for AI words and store only matching comment text."""
    comments_scanned = 0
    comments_ai_mentions = 0
    ai_comment_texts = []
    next_page_token = None

    while comments_scanned < limit:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, limit - comments_scanned),
            "textFormat": "plainText",
            "key": api_key,
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            print(f"  Comment scan failed: {exc}")
            break

        if response.status_code in (403, 404):
            break

        if not response.ok:
            print(f"  Comment scan API error {response.status_code}: {response.text[:200]}")
            break

        data = response.json()
        items = data.get("items", [])

        if not items:
            break

        for item in items:
            snippet = (
                item.get("snippet", {})
                .get("topLevelComment", {})
                .get("snippet", {})
            )
            text = snippet.get("textOriginal") or snippet.get("textDisplay") or ""

            comments_scanned += 1

            matches = matched_ai_words(text)
            if matches:
                comments_ai_mentions += 1
                ai_comment_texts.append(
                    {
                        "matched_words": matches,
                        "text": text,
                    }
                )

            if comments_scanned >= limit:
                break

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return {
        "comments_scanned": str(comments_scanned),
        "comments_ai_mentions": str(comments_ai_mentions),
        "ai_comment_texts": ai_comment_texts,
    }


def fetch_metadata(video_id: str, api_key: str, scan_comments: bool = True) -> dict:
    metadata = {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }

    video_params = {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "key": api_key,
    }

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params=video_params,
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Video API error {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    items = data.get("items", [])

    if not items:
        raise RuntimeError("No video found for this ID")

    item = items[0]
    snippet = item.get("snippet", {})
    content_details = item.get("contentDetails", {})
    statistics = item.get("statistics", {})

    metadata.update(
        {
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "video_description": snippet.get("description", ""),
            "upload_date": snippet.get("publishedAt", ""),
            "duration": parse_iso8601_duration(content_details.get("duration", "")),
            "views": statistics.get("viewCount", ""),
            "likes": statistics.get("likeCount", ""),
            "comments": statistics.get("commentCount", ""),
            "thumbnail_url": (
                snippet.get("thumbnails", {})
                .get("medium", {})
                .get("url", "")
            ),
        }
    )

    channel_id = snippet.get("channelId", "")

    if channel_id:
        channel_params = {
            "part": "snippet,statistics",
            "id": channel_id,
            "key": api_key,
        }

        channel_response = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params=channel_params,
            timeout=15,
        )

        if channel_response.ok:
            channel_data = channel_response.json()
            channel_items = channel_data.get("items", [])

            if channel_items:
                channel_item = channel_items[0]
                channel_snippet = channel_item.get("snippet", {})
                channel_stats = channel_item.get("statistics", {})

                metadata.update(
                    {
                        "subscribers": channel_stats.get("subscriberCount", ""),
                        "channel_video_count": channel_stats.get("videoCount", ""),
                        "channel_view_count": channel_stats.get("viewCount", ""),
                        "channel_description": channel_snippet.get("description", ""),
                        "channel_published_at": channel_snippet.get("publishedAt", ""),
                        "channel_custom_url": channel_snippet.get("customUrl", ""),
                        "channel_country": channel_snippet.get("country", ""),
                    }
                )

    if scan_comments:
        metadata.update(fetch_ai_comment_mentions(video_id, api_key, COMMENT_SCAN_LIMIT))

    return metadata


def load_notes() -> list:
    if not NOTES_PATH.exists():
        raise FileNotFoundError(f"Could not find {NOTES_PATH}")

    with open(NOTES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_notes(notes: list) -> None:
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


def make_backup() -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = BACKUP_DIR / f"before_backfill_{timestamp}.json"
    shutil.copy(NOTES_PATH, backup_path)
    return backup_path


def note_needs_backfill(note: dict, force_comments: bool = False) -> bool:
    if not note.get("id") and note.get("url"):
        return True

    if not note.get("id"):
        return False

    fields_to_check = [
        "upload_date",
        "duration",
        "views",
        "likes",
        "comments",
        "subscribers",
        "thumbnail_url",
        "video_description",
        "channel_video_count",
        "channel_view_count",
        "channel_description",
        "channel_published_at",
        "channel_custom_url",
        "channel_country",
    ]

    if force_comments:
        return (
            note.get("id")
            and int(note.get("comments_ai_mentions") or 0) > 0
            and not note.get("ai_comment_texts")
        )

    return any(not note.get(field) for field in fields_to_check)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill YouTube API metadata into existing notes.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing notes.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of notes to update in this run",
    )
    parser.add_argument(
        "--force-comments",
        action="store_true",
        help="Re-scan comments even if comments_scanned already exists",
    )
    parser.add_argument(
        "--skip-comments",
        action="store_true",
        help="Do not scan comments in this run",
    )
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY is not set. Run:\n"
            "export YOUTUBE_API_KEY=\"your_key_here\""
        )

    notes = load_notes()

    print(f"Loaded {len(notes)} notes from {NOTES_PATH}")

    candidates = []
    for index, note in enumerate(notes):
        if not note.get("id") and note.get("url"):
            note["id"] = extract_video_id(note["url"])

        if note_needs_backfill(note, force_comments=args.force_comments):
            candidates.append((index, note))

    if args.limit is not None:
        candidates = candidates[: args.limit]

    print(f"Notes needing backfill in this run: {len(candidates)}")

    if args.dry_run:
        for index, note in candidates:
            print(f"- Would update #{index}: {note.get('title') or note.get('url') or note.get('channel')}")
        return

    if not candidates:
        print("Nothing to update.")
        return

    backup_path = make_backup()
    print(f"Backup created: {backup_path}")

    updated = 0
    failed = 0

    for index, note in candidates:
        video_id = note.get("id") or extract_video_id(note.get("url", ""))

        if not video_id:
            print(f"Skipping #{index}: no video ID")
            continue

        print(f"Fetching #{index}: {video_id} — {note.get('title') or note.get('channel') or ''}")

        try:
            metadata = fetch_metadata(
                video_id,
                api_key,
                scan_comments=not args.skip_comments,
            )
        except Exception as exc:
            failed += 1
            print(f"  Failed: {exc}")
            continue

        # Preserve your manual coding fields; update only API metadata/comment fields.
        for key, value in metadata.items():
            if value is not None:
                note[key] = value

        updated += 1
        print("  Updated")

    save_notes(notes)

    print()
    print(f"Done. Updated: {updated}. Failed: {failed}.")
    print(f"Backup is here: {backup_path}")
    print(f"Updated file: {NOTES_PATH}")


if __name__ == "__main__":
    main()
