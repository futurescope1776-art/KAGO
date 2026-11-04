#!/usr/bin/env python3
"""
Future of Work and Money — Daily Social Media Automation

Weekday niche rotation:
  MON = Personal Finance for 20s and 30s
  TUE = AI Tools for Side Hustles
  WED = Productivity Systems
  THU = Career Growth and Interview Skills
  FRI = Budget Tech and Digital Tools

Each run:
  1. Detect weekday → pick niche
  2. Generate 30-sec viral script via OpenAI (JSON)
  3. Build 1080x1920 vertical video (gTTS + Pexels clips + MoviePy captions)
  4. Post to YouTube Shorts
  5. Post to Facebook Page Reel
  6. Store artifacts and append to posting log
"""

import datetime
import json
import logging
import os
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Logging — both console and file (file created after output/ exists)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NICHES = {
    0: "Personal Finance for 20s and 30s",
    1: "AI Tools for Side Hustles",
    2: "Productivity Systems",
    3: "Career Growth and Interview Skills",
    4: "Budget Tech and Digital Tools",
}

# Pexels portrait search terms per niche index
PEXELS_QUERIES = {
    0: ["money saving millennials", "personal finance", "budgeting"],
    1: ["AI laptop productivity", "side hustle freelance", "tech startup"],
    2: ["productivity workspace planner", "organized desk", "time management"],
    3: ["job interview professional", "career office meeting", "business success"],
    4: ["smartphone gadgets", "digital technology budget", "tech devices"],
}

TARGET_W, TARGET_H = 1080, 1920


# ---------------------------------------------------------------------------
# Step 1: Niche detection
# ---------------------------------------------------------------------------
def get_todays_niche() -> tuple[int, str]:
    weekday = datetime.date.today().weekday()  # 0=Mon, 6=Sun
    idx = weekday if weekday < 5 else 0        # Weekends fall back to Monday
    return idx, NICHES[idx]


# ---------------------------------------------------------------------------
# Step 2: Script generation via OpenAI
# ---------------------------------------------------------------------------
def generate_script(niche: str) -> dict:
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""You are a viral short-form video scriptwriter for the brand "Future of Work and Money".
Brand mission: help people in their 20s and 30s build wealth, leverage AI, and grow their careers.

Niche for today: {niche}

Write a 30-second YouTube Shorts / Facebook Reels script. Rules:
- First 2 seconds: bold, pattern-interrupting hook (question, shocking stat, or bold claim)
- Body: ONE specific, actionable tip viewers can use TODAY
- Closing CTA: tell them to like, follow, save, or comment
- Tone: casual, energetic, friend-to-friend — not corporate
- Voiceover must be ≤120 words (spoken in ~30 seconds at normal pace)

Respond with ONLY valid JSON in this exact shape:
{{
  "title": "Catchy title under 60 characters, no hashtags",
  "voiceover_text": "Full spoken script — hook, tip, CTA",
  "caption": "2-3 sentence social caption, conversational",
  "hashtags": "#tag1 #tag2 #tag3 ... (8 to 12 relevant hashtags)"
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    logger.info("Script generated: %s", data.get("title"))
    return data


# ---------------------------------------------------------------------------
# Step 3a: TTS with gTTS
# ---------------------------------------------------------------------------
def generate_tts(text: str, out_path: str) -> None:
    from gtts import gTTS

    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(out_path)
    logger.info("TTS saved → %s", out_path)


# ---------------------------------------------------------------------------
# Step 3b: Pexels clip download
# ---------------------------------------------------------------------------
def _download_clip(url: str, dest: str) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=90)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logger.info("Downloaded clip → %s", dest)
        return True
    except Exception as exc:
        logger.warning("Clip download failed (%s): %s", url[:60], exc)
        return False


def fetch_pexels_clips(niche_idx: int, count: int = 3) -> list[str]:
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        logger.warning("PEXELS_API_KEY not set — skipping clip download")
        return []

    headers = {"Authorization": api_key}
    collected: list[str] = []
    queries = PEXELS_QUERIES.get(niche_idx, ["business technology"])

    for query in queries:
        if len(collected) >= count:
            break
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={
                    "query": query,
                    "orientation": "portrait",
                    "size": "medium",
                    "per_page": 6,
                },
                timeout=30,
            )
            resp.raise_for_status()
            for video in resp.json().get("videos", []):
                if len(collected) >= count:
                    break
                for vf in video.get("video_files", []):
                    if (
                        vf.get("file_type") == "video/mp4"
                        and vf.get("quality") in ("hd", "sd")
                        and vf.get("link")
                    ):
                        dest = f"output/clip_{len(collected)}.mp4"
                        if _download_clip(vf["link"], dest):
                            collected.append(dest)
                        break
        except Exception as exc:
            logger.warning("Pexels search error for '%s': %s", query, exc)

    logger.info("Fetched %d Pexels clips", len(collected))
    return collected


# ---------------------------------------------------------------------------
# Step 3c: Build 1080x1920 video with MoviePy
# ---------------------------------------------------------------------------
def _resize_crop(clip, w: int, h: int):
    """Resize then centre-crop clip to exact w×h."""
    ratio_clip = clip.w / clip.h
    ratio_target = w / h
    if ratio_clip > ratio_target:
        new_h, new_w = h, int(clip.w * h / clip.h)
    else:
        new_w, new_h = w, int(clip.h * w / clip.w)
    clip = clip.resize((new_w, new_h))
    x1 = (new_w - w) // 2
    y1 = (new_h - h) // 2
    return clip.crop(x1=x1, y1=y1, x2=x1 + w, y2=y1 + h)


def build_video(clip_paths: list[str], audio_path: str, script_data: dict, out_path: str) -> None:
    from moviepy.editor import (
        AudioFileClip,
        ColorClip,
        CompositeVideoClip,
        TextClip,
        VideoFileClip,
        concatenate_videoclips,
    )

    audio = AudioFileClip(audio_path)
    duration = audio.duration
    logger.info("Audio duration: %.1fs", duration)

    # --- video background ---
    bg_clips = []
    for path in clip_paths:
        try:
            c = VideoFileClip(path, audio=False)
            c = _resize_crop(c, TARGET_W, TARGET_H)
            bg_clips.append(c)
        except Exception as exc:
            logger.warning("Could not load %s: %s", path, exc)

    if not bg_clips:
        logger.warning("No video clips — using solid background")
        bg_clips = [ColorClip((TARGET_W, TARGET_H), color=(15, 15, 50), duration=duration)]

    bg = concatenate_videoclips(bg_clips, method="compose")

    # Loop background if shorter than audio
    if bg.duration < duration:
        loops = int(duration / bg.duration) + 1
        bg = concatenate_videoclips([bg] * loops, method="compose")
    bg = bg.subclip(0, duration)

    # --- caption overlay ---
    words = script_data["voiceover_text"].split()
    chunk_size = 8
    chunks = [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]
    seg_dur = duration / max(len(chunks), 1)

    text_layers = []

    # Voiceover captions
    for i, chunk in enumerate(chunks):
        try:
            tc = (
                TextClip(
                    chunk,
                    fontsize=52,
                    color="white",
                    stroke_color="black",
                    stroke_width=3,
                    font="DejaVu-Sans-Bold",
                    method="caption",
                    size=(TARGET_W - 80, None),
                    align="center",
                )
                .set_start(i * seg_dur)
                .set_duration(seg_dur)
                .set_position(("center", int(TARGET_H * 0.72)))
            )
            text_layers.append(tc)
        except Exception as exc:
            logger.warning("Caption chunk %d skipped: %s", i, exc)

    # Brand watermark
    try:
        brand = (
            TextClip(
                "Future of Work & Money",
                fontsize=36,
                color="white",
                stroke_color="black",
                stroke_width=2,
                font="DejaVu-Sans-Bold",
                method="label",
            )
            .set_duration(duration)
            .set_position(("center", 72))
        )
        text_layers.append(brand)
    except Exception as exc:
        logger.warning("Brand watermark skipped: %s", exc)

    final = CompositeVideoClip([bg] + text_layers).set_audio(audio)
    final.write_videofile(
        out_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        logger=None,
    )
    logger.info("Video written → %s", out_path)


# ---------------------------------------------------------------------------
# Step 4: YouTube Shorts upload
# ---------------------------------------------------------------------------
def upload_youtube(script_data: dict, niche: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    title = f"[{niche}] - {script_data['title']} | Future of Work and Money"[:100]
    description = (
        f"{script_data['caption']}\n\n"
        f"{script_data['hashtags']}\n\n"
        "Future of Work and Money — helping 20s & 30s build wealth with AI and smart systems.\n\n#Shorts"
    )

    base_tags = ["future of work", "money", "personal finance", "AI", "side hustle", "productivity", "career", "budget tech"]
    extra_tags = [t.lstrip("#") for t in script_data["hashtags"].split() if t.startswith("#")]
    tags = list(dict.fromkeys(base_tags + extra_tags))[:30]

    try:
        req = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "27",  # Education
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
            media_body=MediaFileUpload("output/final_video.mp4", chunksize=-1, resumable=True),
        )
        resp = req.execute()
        video_id = resp["id"]
        url = f"https://youtube.com/shorts/{video_id}"
        logger.info("YouTube upload OK → %s", url)
        return url
    except HttpError as exc:
        logger.error("YouTube API error: %s", exc.content)
        raise


# ---------------------------------------------------------------------------
# Step 5: Facebook Page Reel upload
# ---------------------------------------------------------------------------
def upload_facebook(script_data: dict) -> str:
    page_id = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_ACCESS_TOKEN"]

    description = f"{script_data['caption']}\n\n{script_data['hashtags']}"
    url = f"https://graph.facebook.com/v19.0/{page_id}/videos"

    with open("output/final_video.mp4", "rb") as f:
        resp = requests.post(
            url,
            data={"description": description, "access_token": token},
            files={"source": f},
            timeout=300,
        )

    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"Facebook API error: {result['error']}")

    video_id = result.get("id", "unknown")
    logger.info("Facebook upload OK — video ID: %s", video_id)
    return video_id


# ---------------------------------------------------------------------------
# Step 6: Persist artifacts and posting log
# ---------------------------------------------------------------------------
def save_artifacts(
    script_data: dict,
    niche: str,
    yt_url: str | None,
    fb_id: str | None,
) -> None:
    out = Path("output")

    with open(out / "script.json", "w") as f:
        json.dump(script_data, f, indent=2)

    with open(out / "caption.txt", "w") as f:
        f.write(f"{script_data['caption']}\n\n{script_data['hashtags']}")

    record = {
        "date": datetime.datetime.utcnow().isoformat() + "Z",
        "niche": niche,
        "title": script_data["title"],
        "youtube_url": yt_url,
        "facebook_video_id": fb_id,
    }

    log_path = out / "posting_log.json"
    history: list = []
    if log_path.exists():
        try:
            with open(log_path) as f:
                history = json.load(f)
        except Exception:
            pass
    history.append(record)
    with open(log_path, "w") as f:
        json.dump(history, f, indent=2)

    logger.info("Artifacts saved. Record: %s", json.dumps(record))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    Path("output").mkdir(exist_ok=True)

    # Add file log handler now that output/ exists
    fh = logging.FileHandler("output/run.log")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(fh)

    # 1 — niche
    niche_idx, niche = get_todays_niche()
    logger.info("=== Future of Work and Money — Daily Pipeline ===")
    logger.info("Niche: %s", niche)

    # 2 — script
    logger.info("Generating script via OpenAI...")
    script_data = generate_script(niche)

    # 3 — TTS
    logger.info("Generating TTS audio...")
    generate_tts(script_data["voiceover_text"], "output/voiceover.mp3")

    # 3 — Pexels clips
    logger.info("Fetching Pexels stock clips...")
    clip_paths = fetch_pexels_clips(niche_idx, count=3)

    # 3 — build video
    logger.info("Building 1080x1920 video...")
    build_video(clip_paths, "output/voiceover.mp3", script_data, "output/final_video.mp4")

    # 4 — YouTube
    yt_url = None
    yt_vars = ["YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"]
    if all(os.getenv(v) for v in yt_vars):
        logger.info("Uploading to YouTube Shorts...")
        try:
            yt_url = upload_youtube(script_data, niche)
        except Exception as exc:
            logger.error("YouTube upload failed: %s", exc)
    else:
        missing = [v for v in yt_vars if not os.getenv(v)]
        logger.warning("Skipping YouTube upload — missing env vars: %s", missing)

    # 5 — Facebook
    fb_id = None
    fb_vars = ["FACEBOOK_PAGE_ID", "FACEBOOK_ACCESS_TOKEN"]
    if all(os.getenv(v) for v in fb_vars):
        logger.info("Uploading to Facebook Page Reel...")
        try:
            fb_id = upload_facebook(script_data)
        except Exception as exc:
            logger.error("Facebook upload failed: %s", exc)
    else:
        missing = [v for v in fb_vars if not os.getenv(v)]
        logger.warning("Skipping Facebook upload — missing env vars: %s", missing)

    # 6 — artifacts
    save_artifacts(script_data, niche, yt_url, fb_id)
    logger.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
