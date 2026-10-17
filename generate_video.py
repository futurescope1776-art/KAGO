#!/usr/bin/env python3
"""Generate vertical 1080x1920 video: TTS voiceover + Pexels stock clips + burned captions."""

import os
import json
import textwrap
import requests
import numpy as np
from pathlib import Path
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
TARGET_W, TARGET_H = 1080, 1920

# Map each niche to Pexels search queries (portrait-friendly subjects)
NICHE_QUERIES = {
    "Personal Finance for 20s and 30s": [
        "money cash wallet",
        "investing stock market",
        "budgeting notebook planning",
        "young professional success",
    ],
    "AI Tools for Side Hustles": [
        "laptop technology coding",
        "artificial intelligence digital",
        "freelancer working home",
        "digital nomad cafe",
    ],
    "Productivity Systems": [
        "organized desk workspace",
        "planning notebook writing",
        "focused person working",
        "morning routine productive",
    ],
    "Career Growth and Interview Skills": [
        "job interview office",
        "professional business handshake",
        "career success woman man",
        "linkedin networking professional",
    ],
    "Budget Tech and Digital Tools": [
        "smartphone apps technology",
        "gadgets tech lifestyle",
        "laptop coffee shop",
        "digital tools productivity",
    ],
}

FALLBACK_QUERIES = ["success motivation", "work productivity", "digital lifestyle"]


def get_queries(niche: str) -> list:
    for key, queries in NICHE_QUERIES.items():
        if key == niche or key in niche or niche in key:
            return queries
    return FALLBACK_QUERIES


def generate_tts(text: str, path: str):
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(path)
    print(f"TTS saved: {path}")


def pexels_search_videos(query: str, per_page: int = 4) -> list:
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def best_video_url(video: dict) -> str | None:
    files = video.get("video_files", [])
    # Prefer portrait files, highest resolution first
    portrait = sorted(
        [f for f in files if f.get("width", 1) < f.get("height", 1)],
        key=lambda f: f.get("width", 0) * f.get("height", 0),
        reverse=True,
    )
    chosen = portrait[0] if portrait else (files[0] if files else None)
    return chosen["link"] if chosen else None


def download_file(url: str, path: str):
    r = requests.get(url, stream=True, timeout=90)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def fetch_clips(niche: str, clip_dir: str, max_clips: int = 4) -> list:
    os.makedirs(clip_dir, exist_ok=True)
    paths = []
    for query in get_queries(niche):
        if len(paths) >= max_clips:
            break
        try:
            videos = pexels_search_videos(query)
            for v in videos:
                if len(paths) >= max_clips:
                    break
                url = best_video_url(v)
                if not url:
                    continue
                dest = os.path.join(clip_dir, f"clip_{len(paths)}.mp4")
                print(f"Downloading clip [{query}] → {dest}")
                download_file(url, dest)
                paths.append(dest)
        except Exception as e:
            print(f"Warning: Pexels query '{query}' failed: {e}")
    return paths


def crop_to_vertical(clip: VideoFileClip) -> VideoFileClip:
    """Center-crop and resize any clip to TARGET_W x TARGET_H."""
    w, h = clip.size
    target_ratio = TARGET_W / TARGET_H  # ~0.5625

    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        clip = clip.crop(x1=(w - new_w) // 2, width=new_w)
    else:
        new_h = int(w / target_ratio)
        clip = clip.crop(y1=(h - new_h) // 2, height=new_h)

    return clip.resize((TARGET_W, TARGET_H))


def render_caption_image(text: str) -> np.ndarray:
    """Render text onto a transparent RGBA PIL image, return as numpy array."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 52)
            break
    if font is None:
        font = ImageFont.load_default()

    lines = textwrap.wrap(text, width=26)
    line_h = 62
    img_h = len(lines) * line_h + 30
    img_w = TARGET_W

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        y = 15 + i * line_h
        # Drop shadow
        draw.text((22, y + 3), line, font=font, fill=(0, 0, 0, 200))
        # Main text
        draw.text((20, y), line, font=font, fill=(255, 255, 255, 255))

    return np.array(img)


def build_caption_clips(voiceover: str, audio_dur: float) -> list:
    words = voiceover.split()
    # ~3 words per second of speech
    words_per_seg = max(3, int(len(words) / audio_dur * 2.2))
    segments = []
    i = 0
    while i < len(words):
        segments.append(" ".join(words[i : i + words_per_seg]))
        i += words_per_seg

    seg_dur = audio_dur / len(segments)
    clips = []
    for idx, seg in enumerate(segments):
        try:
            arr = render_caption_image(seg)
            h = arr.shape[0]
            ic = (
                ImageClip(arr, ismask=False)
                .set_duration(seg_dur)
                .set_start(idx * seg_dur)
                .set_position(("center", TARGET_H - h - 110))
            )
            clips.append(ic)
        except Exception as e:
            print(f"Warning: caption segment {idx} failed: {e}")
    return clips


def assemble_video(clip_paths: list, audio_dur: float) -> VideoFileClip:
    total_dur = audio_dur + 0.5
    segment_dur = total_dur / len(clip_paths)

    processed = []
    for path in clip_paths:
        try:
            c = VideoFileClip(path, audio=False)
            c = crop_to_vertical(c)
            if c.duration < segment_dur:
                c = c.loop(duration=segment_dur)
            else:
                c = c.subclip(0, segment_dur)
            processed.append(c)
        except Exception as e:
            print(f"Warning: could not process {path}: {e}")

    if not processed:
        raise RuntimeError("No stock clips could be processed")

    base = concatenate_videoclips(processed, method="compose")
    if base.duration < total_dur:
        base = base.loop(duration=total_dur)
    return base.subclip(0, total_dur)


def main():
    os.makedirs("output", exist_ok=True)

    with open("output/script.json") as f:
        script = json.load(f)

    niche = script["niche"]
    voiceover = script["voiceover_text"]
    caption_text = script["caption"]
    hashtags = script["hashtags"]

    print(f"Building video for niche: {niche}")

    # 1. TTS voiceover
    tts_path = "output/voiceover.mp3"
    generate_tts(voiceover, tts_path)
    audio = AudioFileClip(tts_path)
    audio_dur = audio.duration
    print(f"Audio duration: {audio_dur:.1f}s")

    # 2. Download stock clips
    clip_paths = fetch_clips(niche, "output/clips")
    if not clip_paths:
        raise RuntimeError("No Pexels clips downloaded — check PEXELS_API_KEY")

    # 3. Assemble base video from clips
    base = assemble_video(clip_paths, audio_dur)

    # 4. Build caption overlay clips
    caption_clips = build_caption_clips(voiceover, audio_dur)

    # 5. Composite: base + captions
    layers = [base] + caption_clips
    final = (
        CompositeVideoClip(layers, size=(TARGET_W, TARGET_H))
        .set_audio(audio)
        .set_duration(base.duration)
    )

    # 6. Export
    video_path = "output/final_video.mp4"
    final.write_videofile(
        video_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast",
        verbose=False,
        logger=None,
    )
    print(f"Video saved: {video_path}")

    # 7. Write caption.txt for Facebook upload step
    with open("output/caption.txt", "w") as f:
        f.write(f"{caption_text}\n\n{hashtags}")
    print("Caption saved: output/caption.txt")


if __name__ == "__main__":
    main()
