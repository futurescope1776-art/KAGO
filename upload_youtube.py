import os
import sys
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

VIDEO_PATH = "video.mp4"


def authenticate_youtube():
    required = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

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


def upload_short(youtube):
    if not os.path.exists(VIDEO_PATH):
        logger.error(f"Video file not found: {VIDEO_PATH}")
        sys.exit(1)

    size_mb = os.path.getsize(VIDEO_PATH) / 1024 / 1024
    logger.info(f"Uploading {VIDEO_PATH} ({size_mb:.1f} MB) as YouTube Short...")

    body = {
        "snippet": {
            "title": "Future of Work & Money #Shorts",
            "description": "Tips for building wealth with AI and smart systems. #Shorts #personalfinance #moneytok",
            "tags": ["shorts", "personalfinance", "moneytok", "future of work", "side hustle"],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True),
        )
        response = request.execute()
        video_id = response.get("id")
        logger.info(f"Uploaded: https://youtu.be/{video_id}")
    except HttpError as e:
        logger.error(f"YouTube API error: {e.content}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    youtube = authenticate_youtube()
    upload_short(youtube)
