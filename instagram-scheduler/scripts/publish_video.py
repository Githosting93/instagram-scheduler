#!/usr/bin/env python3
"""
publish_video.py

Picks the next video sitting in videos/queue/, publishes it to Instagram
as a Reel via the Graph API, then moves the video (+ its caption file)
into videos/posted/ so the GitHub Action can commit the change and it
won't be posted again.

Required environment variables:
  IG_ACCESS_TOKEN      Long-lived Instagram access token
  IG_BUSINESS_ID       Your Instagram Business Account ID (numeric)
  GITHUB_REPOSITORY    e.g. "yourname/instagram-scheduler" (auto-set in Actions)
  GITHUB_REF_NAME      Branch name, e.g. "main" (auto-set in Actions)

Optional:
  GRAPH_API_VERSION    Defaults to "v21.0"
  MAX_POLL_SECONDS     Defaults to 300 (how long to wait for container to finish processing)

Dry run (no real credentials or API calls needed):
  python scripts/publish_video.py --dry-run
  Walks through picking the next video, building its URL, and reading its
  caption, then prints what WOULD be sent to Instagram -- without calling
  the API or moving any files. Use this to sanity-check the pipeline before
  wiring up real secrets.
"""

import os
import sys
import time
import pathlib
import argparse
import requests

QUEUE_DIR = pathlib.Path("videos/queue")
POSTED_DIR = pathlib.Path("videos/posted")
CAPTIONS_DIR = pathlib.Path("captions")

GRAPH_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

VIDEO_EXTENSIONS = {".mp4", ".mov"}


def env_or_die(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: missing required environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return val


def next_video() -> pathlib.Path | None:
    candidates = sorted(
        p for p in QUEUE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    return candidates[0] if candidates else None


def caption_for(video_path: pathlib.Path) -> str:
    caption_path = CAPTIONS_DIR / f"{video_path.stem}.txt"
    if caption_path.exists():
        return caption_path.read_text(encoding="utf-8").strip()
    return ""


def build_raw_url(video_path: pathlib.Path) -> str:
    repo = env_or_die("GITHUB_REPOSITORY")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    # Public raw GitHub URL -- repo MUST be public, or this URL is not
    # fetchable by Meta's servers.
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{video_path.as_posix()}"


def create_container(ig_user_id: str, token: str, video_url: str, caption: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=60,
    )
    data = resp.json()
    if "id" not in data:
        print(f"ERROR creating container: {data}", file=sys.stderr)
        sys.exit(1)
    return data["id"]


def wait_for_container(container_id: str, token: str) -> None:
    max_seconds = int(os.environ.get("MAX_POLL_SECONDS", "300"))
    waited = 0
    interval = 10
    while waited < max_seconds:
        resp = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        )
        data = resp.json()
        status = data.get("status_code")
        print(f"Container status: {status} (waited {waited}s)")
        if status == "FINISHED":
            return
        if status == "ERROR":
            print(f"ERROR: container processing failed: {data}", file=sys.stderr)
            sys.exit(1)
        time.sleep(interval)
        waited += interval
    print("ERROR: timed out waiting for video container to finish processing", file=sys.stderr)
    sys.exit(1)


def publish_container(ig_user_id: str, token: str, container_id: str) -> str:
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    data = resp.json()
    if "id" not in data:
        print(f"ERROR publishing container: {data}", file=sys.stderr)
        sys.exit(1)
    return data["id"]


def move_to_posted(video_path: pathlib.Path) -> None:
    POSTED_DIR.mkdir(parents=True, exist_ok=True)
    dest = POSTED_DIR / video_path.name
    video_path.rename(dest)

    caption_path = CAPTIONS_DIR / f"{video_path.stem}.txt"
    if caption_path.exists():
        posted_captions = CAPTIONS_DIR / "posted"
        posted_captions.mkdir(parents=True, exist_ok=True)
        caption_path.rename(posted_captions / caption_path.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be posted without calling the Instagram API or moving files.",
    )
    args = parser.parse_args()

    video_path = next_video()
    if video_path is None:
        print("No videos in queue. Nothing to post today.")
        return

    caption = caption_for(video_path)
    video_url = build_raw_url(video_path)

    if args.dry_run:
        print("=== DRY RUN (no API calls made, no files moved) ===")
        print(f"Would publish: {video_path.name}")
        print(f"Video size: {video_path.stat().st_size / 1_000_000:.2f} MB")
        print(f"Video URL (must be public): {video_url}")
        print(f"Caption:\n{caption}")
        print("=== End dry run ===")
        return

    token = env_or_die("IG_ACCESS_TOKEN")
    ig_user_id = env_or_die("IG_BUSINESS_ID")

    print(f"Publishing: {video_path.name}")
    print(f"Video URL: {video_url}")
    print(f"Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")

    container_id = create_container(ig_user_id, token, video_url, caption)
    print(f"Created container {container_id}, waiting for processing...")
    wait_for_container(container_id, token)

    media_id = publish_container(ig_user_id, token, container_id)
    print(f"Published! Media ID: {media_id}")

    move_to_posted(video_path)
    print(f"Moved {video_path.name} to videos/posted/")


if __name__ == "__main__":
    main()
