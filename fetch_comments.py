"""
Fetch all top-level comments (and replies) from a single YouTube video.
Saves raw comment data to data/comments_<video_id>.json

Usage:
    python fetch_comments.py --video-id <VIDEO_ID>

Requires YOUTUBE_API_KEY in .env
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

API_KEY = os.environ["YOUTUBE_API_KEY"]


def fetch_comment_threads(youtube, video_id: str) -> list[dict]:
    comments = []
    page_token = None

    while True:
        response = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=100,
            pageToken=page_token,
            textFormat="plainText",
        ).execute()

        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comment = {
                "comment_id": item["id"],
                "video_id": video_id,
                "parent_id": None,
                "text": top["textDisplay"],
                "author_channel_id": top.get("authorChannelId", {}).get("value"),
                "like_count": top.get("likeCount", 0),
                "published_at": top["publishedAt"],
                "reply_count": item["snippet"]["totalReplyCount"],
            }
            comments.append(comment)

            # Include replies if present
            for reply_item in item.get("replies", {}).get("comments", []):
                r = reply_item["snippet"]
                comments.append({
                    "comment_id": reply_item["id"],
                    "video_id": video_id,
                    "parent_id": item["id"],
                    "text": r["textDisplay"],
                    "author_channel_id": r.get("authorChannelId", {}).get("value"),
                    "like_count": r.get("likeCount", 0),
                    "published_at": r["publishedAt"],
                    "reply_count": 0,
                })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return comments


def get_video_title(youtube, video_id: str) -> str:
    response = youtube.videos().list(part="snippet", id=video_id).execute()
    items = response.get("items", [])
    return items[0]["snippet"]["title"] if items else "Unknown"


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube comments for one video.")
    parser.add_argument("--video-id", required=True, help="YouTube video ID (e.g. dQw4w9WgXcQ)")
    args = parser.parse_args()
    video_id = args.video_id

    youtube = build("youtube", "v3", developerKey=API_KEY)

    print(f"Fetching comments for video: {video_id}")
    title = get_video_title(youtube, video_id)
    print(f"Title: {title}")

    comments = fetch_comment_threads(youtube, video_id)
    print(f"Fetched {len(comments)} comments (including replies)")

    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"comments_{video_id}.json"

    payload = {
        "video_id": video_id,
        "title": title,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "comment_count": len(comments),
        "comments": comments,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
