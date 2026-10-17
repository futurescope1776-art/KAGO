#!/usr/bin/env python3
"""Detect weekday, pick niche, generate viral 30-sec script via OpenAI."""

import os
import json
import datetime
from openai import OpenAI

NICHES = {
    0: "Personal Finance for 20s and 30s",   # Monday
    1: "AI Tools for Side Hustles",           # Tuesday
    2: "Productivity Systems",                # Wednesday
    3: "Career Growth and Interview Skills",  # Thursday
    4: "Budget Tech and Digital Tools",       # Friday
    5: "Personal Finance for 20s and 30s",   # Saturday → Mon niche
    6: "AI Tools for Side Hustles",           # Sunday → Tue niche
}

NICHE_CONTEXT = {
    "Personal Finance for 20s and 30s": "budgeting, saving, investing, debt payoff, emergency funds, Roth IRA",
    "AI Tools for Side Hustles": "ChatGPT, automation, freelancing, passive income, AI writing, prompt engineering",
    "Productivity Systems": "time blocking, second brain, Notion, deep work, morning routines, GTD",
    "Career Growth and Interview Skills": "salary negotiation, LinkedIn, résumé, behavioral interviews, networking, promotions",
    "Budget Tech and Digital Tools": "affordable software, free tools, cashback apps, refurbished tech, subscription cuts",
}


def get_niche():
    weekday = datetime.datetime.now().weekday()
    return NICHES[weekday], weekday


def generate_script(niche: str) -> dict:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    context = NICHE_CONTEXT.get(niche, "")
    prompt = f"""Create a viral 30-second YouTube Shorts / TikTok script for the niche: "{niche}"
Brand: Future of Work and Money
Target audience: People in their 20s and 30s building wealth and careers.
Relevant topics: {context}

Requirements:
- HOOK in the FIRST 2 seconds — bold claim, shocking stat, or direct question
- One clear, actionable tip that delivers real value
- Strong CTA at the end (follow for more, save this, comment below)
- Conversational, upbeat, direct tone — like a smart friend giving advice
- Voiceover must be under 80 words (aim for ~65 words for 30 sec pacing)

Return ONLY valid JSON with exactly these fields:
{{
  "title": "Catchy short title max 55 chars, no niche prefix, no emoji",
  "voiceover_text": "Full spoken script under 80 words",
  "caption": "Social media caption 2-3 engaging sentences with a hook",
  "hashtags": "#tag1 #tag2 #tag3 (10-15 relevant hashtags, space-separated)"
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.9,
    )

    return json.loads(response.choices[0].message.content)


def build_youtube_title(niche: str, title: str) -> str:
    prefix = f"[{niche}] - "
    suffix = " | Future of Work and Money"
    max_middle = 100 - len(prefix) - len(suffix)
    return f"{prefix}{title[:max_middle]}{suffix}"


def main():
    os.makedirs("output", exist_ok=True)

    niche, weekday = get_niche()
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    print(f"Weekday: {day_names[weekday]} → Niche: {niche}")

    script = generate_script(niche)
    script["niche"] = niche
    script["weekday"] = day_names[weekday]
    script["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    script["youtube_title"] = build_youtube_title(niche, script["title"])

    output_path = "output/script.json"
    with open(output_path, "w") as f:
        json.dump(script, f, indent=2)

    print(f"Script saved: {output_path}")
    print(f"Title: {script['title']}")
    print(f"YouTube title: {script['youtube_title']}")
    print(f"Voiceover ({len(script['voiceover_text'].split())} words):")
    print(f"  {script['voiceover_text']}")


if __name__ == "__main__":
    main()
