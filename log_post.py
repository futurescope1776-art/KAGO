#!/usr/bin/env python3
"""Append a post record to output/post_log.json and print a summary."""

import json
import os
import datetime


def main():
    os.makedirs("output", exist_ok=True)

    script: dict = {}
    if os.path.exists("output/script.json"):
        try:
            with open("output/script.json") as f:
                script = json.load(f)
        except Exception as e:
            print(f"Warning: could not read script.json: {e}")

    entry = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": script.get("date", datetime.datetime.now().strftime("%Y-%m-%d")),
        "weekday": script.get("weekday", "Unknown"),
        "niche": script.get("niche", "Unknown"),
        "title": script.get("title", ""),
        "youtube_title": script.get("youtube_title", ""),
        "platforms": ["YouTube Shorts", "Facebook Page Reel"],
        "status": "posted",
    }

    log_path = "output/post_log.json"
    log: list = []
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                log = json.load(f)
        except Exception:
            log = []

    log.append(entry)

    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)

    print("=== POST SUMMARY ===")
    print(f"Date      : {entry['date']} ({entry['weekday']})")
    print(f"Niche     : {entry['niche']}")
    print(f"Title     : {entry['title']}")
    print(f"YT Title  : {entry['youtube_title']}")
    print(f"Platforms : {', '.join(entry['platforms'])}")
    print(f"Log saved : {log_path} ({len(log)} total entries)")


if __name__ == "__main__":
    main()
