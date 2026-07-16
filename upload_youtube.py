import os
import pickle
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# Get from ai-social context
CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

# Find video to upload
VIDEO_FILE = None
for path in ["./video.mp4", "./short.mp4", "./videos/short.mp4", "./output.mp4"]:
    if os.path.exists(path):
        VIDEO_FILE = path
        break

if not VIDEO_FILE:
    # find any mp4
    import glob
    mp4s = glob.glob("**/*.mp4", recursive=True)
    if mp4s:
        VIDEO_FILE = mp4s[0]

if not VIDEO_FILE:
    raise Exception("No.mp4 found. Put your short as video.mp4 in repo root")

print(f"Uploading: {VIDEO_FILE}")

creds = Credentials(
    None,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scopes=["https://www.googleapis.com/auth/youtube.upload"]
)
creds.refresh(Request())

youtube = build("youtube", "v3", credentials=creds)

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": "Future Work Money - Daily Short #1",
            "description": "Auto-uploaded via CircleCI #KAGO1 #FutureWorkMoney",
            "tags": ["future work", "money", "AI", "shorts"],
            "categoryId": "28"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True)
)

response = request.execute()
print(f"✅ YouTube Short uploaded! Video ID: {response['id']}")
print(f"https://youtube.com/shorts/{response['id']}")
