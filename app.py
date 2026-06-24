"""
YouTube  - narrative analysis tools
----------------------

This Flask application runs on your local machine and provides a simple web
interface for capturing notes about YouTube videos. The idea is that you can
watch videos in another browser window, copy the video's URL, and paste it
into this tool. The application will attempt to fetch basic metadata about
the video (title, channel name, duration, view count and other statistics)
using the YouTube Data API if a key is provided via the `YOUTUBE_API_KEY`
environment variable. If no key is available it falls back to the official
oEmbed endpoint which exposes the title and channel name. After fetching
metadata the tool displays a form where you can add your own notes. Those
notes are persisted to a local JSON file (`notes.json`) in the same
directory.

To run this application, install Flask (`pip install flask`) and optionally
requests (`pip install requests`) if not already installed. Then start
the server with:

    python app.py

Navigate to http://localhost:9876 in your browser. Paste a YouTube URL and
record your notes.

"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
import shutil
from collections import Counter

import requests
from flask import Flask, render_template, request, redirect, url_for, flash


app = Flask(__name__)

# A secret key is required for flashing messages. In production you should
# override this with a more secure random value (for example via an
# environment variable).
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")

# Path to the notes file. This file is used to persist all captured notes.
BASE_DIR = Path(__file__).resolve().parent
NOTES_PATH = BASE_DIR / "notes.json"
BACKUP_DIR = BASE_DIR / "backedup_notes"
BACKUP_DIR.mkdir(exist_ok=True)
MAX_BACKUPS = 80

# Scan all top-level comments by paging through YouTube's API.
# YouTube allows maxResults=100 per request; that is the page size, not a total limit.
AI_COMMENT_WORDS = ["ai", "clanker", "slop", "chatgpt", "bot",
                    "ki", "skvip", "feik", "bott",
                    "openai", "claude", "anthropic", "sora", "nanobanana",
                    "scripted", "fake",
                    ]


def extract_video_id(url: str) -> str:
    """Extract the video ID from a YouTube URL.

    Supports standard YouTube URLs (youtube.com/watch?v=...), shorts URLs
    (youtube.com/shorts/...), and youtu.be short links. Returns an empty
    string if no ID can be determined.
    """
    if not url:
        return ""
    # Match various YouTube URL formats
    # Standard watch URL: v parameter
    match = re.search(r"v=([\w-]{11})", url)
    if match:
        return match.group(1)
    # Shortened youtu.be link
    match = re.search(r"youtu\.be/([\w-]{11})", url)
    if match:
        return match.group(1)
    # Shorts URL: /shorts/<id>
    match = re.search(r"shorts/([\w-]{11})", url)
    if match:
        return match.group(1)
    return ""


def parse_iso8601_duration(duration: str) -> str:
    """Convert an ISO 8601 duration (e.g. PT5M10S) into HH:MM:SS format.

    This helper uses a simple regular expression to extract hours, minutes
    and seconds. If the duration string is invalid it returns an empty
    string. Leading zeroes are added for minutes and seconds when
    appropriate.
    """
    if not duration or not duration.startswith("PT"):
        return ""
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
    match = pattern.match(duration)
    if not match:
        return ""
    hours, minutes, seconds = match.groups()
    h = int(hours) if hours else 0
    m = int(minutes) if minutes else 0
    s = int(seconds) if seconds else 0
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    else:
        return f"{m:d}:{s:02d}"



def matched_ai_words(text: str) -> list:
    """Return AI-related keywords found in a comment."""
    if not text:
        return []

    matches = []

    for word in AI_COMMENT_WORDS:
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(word)

    return matches


def comment_mentions_ai_words(text: str) -> bool:
    """Return True if a comment mentions one of the selected AI-related keywords."""
    return bool(matched_ai_words(text))


def fetch_ai_comment_mentions(video_id: str, api_key: str) -> dict:
    """Scan all available top-level comments for AI-related words.

    YouTube returns comments in pages. maxResults=100 is the API's per-request
    maximum, not the total scan limit. This function keeps requesting pages
    until YouTube stops returning nextPageToken.

    Matching comment text is saved in ai_comment_texts.
    """
    comments_scanned = 0
    comments_ai_mentions = 0
    ai_comment_texts = []
    next_page_token = None

    while True:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "textFormat": "plainText",
            "key": api_key,
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/commentThreads",
                params=params,
                timeout=10,
            )
        except Exception:
            break

        if not resp.ok:
            break

        data = resp.json()
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

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return {
        "comments_scanned": str(comments_scanned),
        "comments_ai_mentions": str(comments_ai_mentions),
        "ai_comment_texts": ai_comment_texts,
    }


def fetch_metadata(video_id: str, scan_comments: bool = False) -> dict:
    """Fetch metadata for a given YouTube video ID.

    Attempts to use the YouTube Data API if an API key is set in the
    environment variable `YOUTUBE_API_KEY`. If no key is available or
    fetching fails for any reason, falls back to YouTube's official oEmbed
    endpoint which provides the title and channel name. If even that fails,
    returns a dictionary with only the URL.

    The returned dictionary includes at minimum the video ID and URL. When
    available it will also include: title, channel, upload date, duration
    (HH:MM:SS), view count, like count, comment count, thumbnail URL and
    subscriber count for the channel.
    """
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    metadata = {
        "id": video_id,
        "url": base_url,
    }

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if api_key:
        # Use the official YouTube Data API to fetch details
        api_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,contentDetails,statistics&id={video_id}&key={api_key}"
        )
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.ok:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    snippet = item.get("snippet", {})
                    content_details = item.get("contentDetails", {})
                    statistics = item.get("statistics", {})
                    metadata.update(
                        {
                            "title": snippet.get("title"),
                            "channel": snippet.get("channelTitle"),
                            "video_description": snippet.get("description"),
                            "upload_date": snippet.get("publishedAt"),
                            "duration": parse_iso8601_duration(
                                content_details.get("duration", "")
                            ),
                            "views": statistics.get("viewCount"),
                            "likes": statistics.get("likeCount"),
                            "comments": statistics.get("commentCount"),
                            "thumbnail_url": snippet.get("thumbnails", {})
                            .get("medium", {})
                            .get("url"),
                        }
                    )

                    # Fetch channel stats to get subscriber count if channel ID is available
                    channel_id = snippet.get("channelId")
                    if channel_id:
                        channel_api = (
                            "https://www.googleapis.com/youtube/v3/channels"
                            f"?part=snippet,statistics&id={channel_id}&key={api_key}"
                        )
                        ch_resp = requests.get(channel_api, timeout=10)
                        if ch_resp.ok:
                            ch_data = ch_resp.json()
                            ch_items = ch_data.get("items", [])
                            if ch_items:
                                channel_item = ch_items[0]
                                channel_snippet = channel_item.get("snippet", {})
                                channel_stats = channel_item.get("statistics", {})

                                metadata["subscribers"] = channel_stats.get("subscriberCount")
                                metadata["channel_video_count"] = channel_stats.get("videoCount")
                                metadata["channel_view_count"] = channel_stats.get("viewCount")
                                metadata["channel_description"] = channel_snippet.get("description")
                                metadata["channel_published_at"] = channel_snippet.get("publishedAt")
                                metadata["channel_custom_url"] = channel_snippet.get("customUrl")
                                metadata["channel_country"] = channel_snippet.get("country")
                # Do not scan comments during ordinary URL fetches.
                # Scanning all comments can take a long time and prevents the note form from loading.
                # Use the backfill/discovery scripts for comment text analysis, or call
                # fetch_metadata(video_id, scan_comments=True) explicitly.
                if scan_comments:
                    metadata.update(fetch_ai_comment_mentions(video_id, api_key))

                return metadata
        except Exception as e:
            print("ERROR fetching YouTube API metadata:", e)
            # Fall back to oEmbed
            pass

    # Fallback: use the oEmbed endpoint (no API key required)
    oembed_url = "https://www.youtube.com/oembed"
    params = {"url": base_url, "format": "json"}
    try:
        resp = requests.get(oembed_url, params=params, timeout=10)
        if resp.ok:
            data = resp.json()
            metadata.update(
                {
                    "title": data.get("title"),
                    "channel": data.get("author_name"),
                    "thumbnail_url": data.get("thumbnail_url"),
                }
            )
    except Exception:
        pass

    return metadata

def backup_notes(notes):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = BACKUP_DIR / f"notes_backup_{timestamp}.json"

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

    print(f"Backup saved: {backup_file}")

    # Delete oldest backups if too many
    backups = sorted(BACKUP_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)

    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        oldest.unlink()
        print(f"Deleted old backup: {oldest}")

def load_notes() -> list:
    """Load all saved notes from the JSON file.

    Returns an empty list if the file does not exist or cannot be parsed.
    """
    if NOTES_PATH.exists():
        try:
            with open(NOTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("ERROR reading notes.json:", e)
            raise
    return []


def save_note(note: dict) -> None:
    """Append a single note to the JSON file.

    The note should be a dictionary with metadata and user-supplied fields.
    Notes are stored as a list of objects.
    """
    notes = load_notes()
    if NOTES_PATH.exists():
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        shutil.copy(
            NOTES_PATH,
            BACKUP_DIR / f"prewrite_{timestamp}.json"
        )
    notes.append(note)
    if len(notes) % 5 == 0:
        backup_notes(notes)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


@app.route("/", methods=["GET"])
def index():
    notes = load_notes()[::-1]

    masterplot_counts = Counter()
    country_counts = Counter()
    tag_counts = Counter()
    audio_counts = Counter()

    for note in notes:
        plot = note.get("masterplot", "").strip()
        if plot:
            masterplot_counts[plot] += 1

        country = note.get("channel_country", "").strip()
        if country:
            country_counts[country] += 1
        else:
            country_counts["Unknown"] += 1

        tags = note.get("tags", "")
        for tag in tags.replace(",", " ").split():
            tag = tag.strip()
            if tag:
                tag_counts[tag] += 1

        for audio in note.get("audio_features", []):
            if audio:
                audio_counts[audio] += 1

    coded_shorts = [
        note for note in notes
        if note.get("ai_confidence")
    ]

    total_coded = len(coded_shorts)

    definite_ai = [
        note for note in coded_shorts
        if note.get("ai_confidence") == "Definite AI"
    ]

    definite_ai_percent = 0
    if total_coded:
        definite_ai_percent = round((len(definite_ai) / total_coded) * 100, 1)

    total_masterplots_coded = sum(masterplot_counts.values())

    masterplot_counts = dict(
        sorted(masterplot_counts.items(), key=lambda x: x[1], reverse=True)
    )

    country_counts = dict(country_counts.most_common())
    tag_counts = dict(tag_counts.most_common(30))
    audio_counts = dict(audio_counts.most_common())

    return render_template(
        "index.html",
        notes=notes,
        total_coded=total_coded,
        definite_ai_count=len(definite_ai),
        definite_ai_percent=definite_ai_percent,
        masterplot_counts=masterplot_counts,
        total_masterplots_coded=total_masterplots_coded,
        country_counts=country_counts,
        tag_counts=tag_counts,
        audio_counts=audio_counts,
    )

@app.route("/fetch", methods=["POST"])
def fetch():
    """Handle the form submission for a new video URL.

    Validates the URL, extracts the video ID and fetches metadata. If
    successful it renders the note-taking form. On failure it flashes an
    error message and redirects back to the home page.
    """
    url = request.form.get("url", "").strip()
    if not url:
        flash("Please provide a YouTube URL.", "error")
        return redirect(url_for("index"))
    video_id = extract_video_id(url)
    if not video_id:
        flash("Could not extract a video ID from that URL.", "error")
        return redirect(url_for("index"))
    metadata = fetch_metadata(video_id, scan_comments=True)
    # Prepopulate the metadata dictionary with empty strings for missing
    # optional fields to simplify template rendering
    defaults = {
        "title": "",
        "channel": "",
        "upload_date": "",
        "duration": "",
        "views": "",
        "likes": "",
        "comments": "",
        "thumbnail_url": "",
        "subscribers": "",
        "video_description": "",
        "channel_video_count": "",
        "channel_view_count": "",
        "channel_description": "",
        "channel_published_at": "",
        "channel_custom_url": "",
        "channel_country": "",
        "comments_scanned": "",
        "comments_ai_mentions": "",
        "ai_comment_texts": [],
    }
    for key, value in defaults.items():
        metadata.setdefault(key, value)
    return render_template("note.html", metadata=metadata)


@app.route("/save", methods=["POST"])
def save():
    """Persist the note entered by the user.

    Reads hidden form fields that contain the metadata and the user-provided
    notes. A timestamp is added for reference. After saving the note the
    user is redirected back to the home page with a success message.
    """
    # Collect metadata from hidden inputs
    meta_fields = [
        "id",
        "url",
        "title",
        "channel",
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
        "comments_scanned",
        "comments_ai_mentions",
        "ai_comment_texts",
    ]
    note_data = {}
    for field in meta_fields:
        note_data[field] = request.form.get(field, "")

    # ai_comment_texts is a list, but hidden form fields arrive as text.
    # If it has been stringified, try to parse it back into a list.
    if isinstance(note_data.get("ai_comment_texts"), str):
        try:
            note_data["ai_comment_texts"] = json.loads(note_data["ai_comment_texts"])
        except Exception:
            note_data["ai_comment_texts"] = []

    # Structured note fields from the form
    note_data["content_type"] = request.form.get("content_type", "")
    note_data["ai_confidence"] = request.form.get("ai_confidence", "")
    note_data["summary"] = request.form.get("summary", "").strip()
    note_data["visuals"] = request.form.get("visuals", "").strip()
    note_data["audio_features"] = request.form.getlist("audio_features")
    # ai_markers is a list of selected checkbox values
    note_data["ai_markers"] = request.form.getlist("ai_markers")
    # Rhetorical narratology fields
    note_data["first_person_narrator"] = "Yes" if request.form.get("first_person_narrator") else ""
    note_data["direct_address"] = "Yes" if request.form.get("direct_address") else ""
    note_data["implied_purpose"] = request.form.get("implied_purpose", "").strip()
    note_data["reliability"] = request.form.get("reliability", "")
    note_data["temporal_stance"] = request.form.get("temporal_stance", "")
    note_data["image_narration_alignment"] = request.form.get("image_narration_alignment", "")
    note_data["masterplot"] = request.form.get("masterplot", "").strip()
    note_data["tags"] = request.form.get("tags", "").strip()
    note_data["notes"] = request.form.get("notes", "").strip()
    # Timestamp for when the note was saved
    note_data["timestamp"] = datetime.utcnow().isoformat()
    save_note(note_data)
    flash("Your note has been saved.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # When run directly, start the development server. In production use a
    # proper WSGI server instead.

    # Determine the port to listen on. If the PORT environment variable is set
    # (e.g. PORT=8000 python app.py), use that value; otherwise default to 5000.
    # This allows users to run the app on a different port when 5000 is already
    # occupied (for example by AirPlay or another service).
    port = int(os.environ.get("PORT", "9876"))
    app.run(debug=True, host="0.0.0.0", port=port)