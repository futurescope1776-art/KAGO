import os
import json
import sys
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load caption from previous step
def load_metadata():
    """Load video metadata from script.json with fallback to caption.txt"""
    script_path = "output/script.json"
    caption_path = "output/caption.txt"
    
    try:
        if os.path.exists(script_path):
            with open(script_path) as f:
                data = json.load(f)
            # Prefer pre-built youtube_title ([Niche] - Title | Future of Work and Money)
            yt_title = data.get("youtube_title") or (data.get("title", "")[:95] + " #Shorts")
            return {
                "title": yt_title[:100].strip(),
                "description": (
                    f"{data.get('caption', '')}\n\n"
                    f"{data.get('hashtags', '')}\n\n"
                    "Future of Work and Money - Helping 20s and 30s build wealth with AI and smart systems."
                ),
                "hashtags": data.get("hashtags", "#personalfinance #moneytok"),
            }
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse script.json: {e}")
    except Exception as e:
        logger.warning(f"Error loading script.json: {e}")

    # Fallback
    caption = "Future of Work and Money"
    if os.path.exists(caption_path):
        try:
            with open(caption_path) as f:
                caption = f.read().strip()
        except Exception as e:
            logger.warning(f"Error reading caption.txt: {e}")

    return {
        "title": "Future of Work and Money #Shorts",
        "description": caption,
        "hashtags": "#personalfinance #moneytok",
    }

def authenticate_youtube():
    """Authenticate with YouTube API"""
    required_env = ["YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"]
    missing = [var for var in required_env if not os.getenv(var)]
    
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
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )
        creds.refresh(Request())
        logger.info("YouTube authentication successful")
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)

def upload_video(youtube, metadata, video_path):
    """Upload video to YouTube"""
    
    # Validate video file
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        sys.exit(1)
    
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        logger.error("Video file is empty")
        sys.exit(1)
    
    logger.info(f"Uploading video ({file_size / 1024 / 1024:.1f} MB)...")
    
    try:
        # Clean up tags: filter empty strings and limit
        tags = ["future of work", "personal finance", "side hustle", "productivity", "career growth", "budget tech"]
        tags.extend([tag.strip() for tag in metadata["hashtags"].split() if tag.strip()])
        tags = tags[:30]  # YouTube limit is 30 tags
        
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": metadata["title"],
                    "description": metadata["description"],
                    "tags": tags,
                    "categoryId": "27"  # Education
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            },
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )
        
        response = request.execute()
        video_id = response.get('id')
        video_url = f"https://youtu.be/{video_id}"
        logger.info(f"Video uploaded successfully: {video_url}")
        return video_url
        
    except HttpError as e:
        logger.error(f"YouTube API error: {e.content}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    metadata = load_metadata()
    youtube = authenticate_youtube()
    upload_video(youtube, metadata, "output/final_video.mp4")
