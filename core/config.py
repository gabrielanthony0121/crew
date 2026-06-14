import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = "c!"

# Persisted via Railway Variables (recommended for production) or data/*.json (local / volume)
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

ALLOWED_ROLE_IDS: list[int] = [
    # Example: 1234567890123456789
]

# Video Crew Chat enforcement (camera required to stay in the voice channel)
# Channel: "video crew chat"
# Prefer setting VIDEO_CREW_CHAT_ID as a Railway Variable so it survives deploys without code changes.
_raw_video_id = os.getenv("VIDEO_CREW_CHAT_ID")
VIDEO_CREW_CHAT_ID: int | None = int(_raw_video_id) if _raw_video_id else 1503224954718781463
CAMERA_GRACE_SECONDS: int = 20

# Moderation Announcements channel (read-only, where the permanent guide embed lives)
# This is the channel ID you provided: 1508675774943723593
MOD_ANNOUNCEMENTS_CHANNEL_ID: int = 1508675774943723593