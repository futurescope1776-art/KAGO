import os
import sys
import json
import logging
import subprocess

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VIDEO_PATH = "video.mp4"
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB
MIN_DURATION = 30


def get_max_duration():
    topic = os.getenv("VIDEO_TOPIC", "").lower()
    long_keywords = {"tutorial", "guide", "explainer", "deep", "how to"}
    short_keywords = {"news", "quick", "tip"}
    if any(k in topic for k in long_keywords):
        return 120
    if any(k in topic for k in short_keywords):
        return 60
    return 120


def probe_video(path):
    """Return (width, height, duration_seconds) via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "stream=width,height,duration",
        "-of", "json", path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except Exception as e:
        logger.error(f"ffprobe failed: {e}")
        sys.exit(1)

    width = height = duration = None
    for stream in data.get("streams", []):
        if stream.get("width") and stream.get("height"):
            width = stream["width"]
            height = stream["height"]
        if stream.get("duration"):
            try:
                duration = float(stream["duration"])
            except ValueError:
                pass

    if width is None or height is None or duration is None:
        logger.error("Could not read video dimensions or duration from ffprobe output")
        sys.exit(1)

    return width, height, duration


def validate_video(path):
    if not os.path.exists(path):
        logger.error(f"Video file not found: {path}")
        sys.exit(1)

    size = os.path.getsize(path)
    if size == 0:
        logger.error("Video file is empty")
        sys.exit(1)
    if size > MAX_FILE_BYTES:
        logger.error(f"File too large: {size / 1024 / 1024:.1f} MB (max 100 MB)")
        sys.exit(1)

    width, height, duration = probe_video(path)

    # Vertical check: height > width, minimum 720x1280
    if height <= width:
        logger.error(f"Video is not vertical: {width}x{height} (height must exceed width)")
        sys.exit(1)
    if width < 720 or height < 1280:
        logger.error(f"Resolution too small: {width}x{height} (minimum 720x1280)")
        sys.exit(1)

    max_duration = get_max_duration()
    if duration < MIN_DURATION:
        logger.error(f"Duration too short: {duration:.1f}s (minimum {MIN_DURATION}s)")
        sys.exit(1)
    if duration > max_duration:
        logger.error(f"Duration too long: {duration:.1f}s (maximum {max_duration}s for VIDEO_TOPIC='{os.getenv('VIDEO_TOPIC', '')}')")
        sys.exit(1)

    logger.info(f"Video validated: {width}x{height}, {duration:.1f}s, {size / 1024 / 1024:.1f} MB")


def authenticate_youtube():
    required = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    try:
        creds = Credentials(
            None,
            refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YOUTUBE_CLIENT_ID"),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds.refresh(Request())
        logger.info("YouTube authentication successful")
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)


def upload_video(youtube, path):
    topic = os.getenv("VIDEO_TOPIC", "Short")
    title = f"{topic} #Shorts"[:100]
    description = "Future of Work and Money - Helping 20s and 30s build wealth with AI and smart systems."

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["shorts", "personalfinance", "moneytok"],
                    "categoryId": "27",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload(path, chunksize=-1, resumable=True),
        )
        response = request.execute()
        video_id = response.get("id")
        logger.info(f"Uploaded: https://youtu.be/{video_id}")
        return video_id
    except HttpError as e:
        logger.error(f"YouTube API error: {e.content}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    validate_video(VIDEO_PATH)
    youtube = authenticate_youtube()
    upload_video(youtube, VIDEO_PATH)
