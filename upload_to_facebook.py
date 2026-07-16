import os
import requests
import sys

# Load environment variables
page_id = os.getenv("FACEBOOK_PAGE_ID")
token = os.getenv("FACEBOOK_ACCESS_TOKEN")

# Validate environment variables
if not page_id or not token:
    print("Error: FACEBOOK_PAGE_ID and FACEBOOK_ACCESS_TOKEN must be set")
    sys.exit(1)

video_path = "output/final_video.mp4"
caption_path = "output/caption.txt"

# Validate files exist
if not os.path.exists(video_path):
    print(f"Error: Video file not found: {video_path}")
    sys.exit(1)

if not os.path.exists(caption_path):
    print(f"Error: Caption file not found: {caption_path}")
    sys.exit(1)

# Read caption
try:
    with open(caption_path) as f:
        caption = f.read().strip()
except Exception as e:
    print(f"Error reading caption: {e}")
    sys.exit(1)

# Upload video
url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
try:
    with open(video_path, 'rb') as f:
        r = requests.post(url, data={
            'description': caption,
            'access_token': token
        }, files={'source': f})
    
    response = r.json()
    
    # Check for API errors
    if 'error' in response:
        print(f"Facebook API Error: {response['error']}")
        sys.exit(1)
    
    print(f"Video uploaded successfully: {response.get('id', 'Unknown ID')}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
