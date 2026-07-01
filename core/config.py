import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# DATA_DIR configuration for persistence
# - Local development: uses ./data relative to project root
# - Railway: set DATA_DIR env var + mount a Volume to that path (recommended: /data)
_data_dir_env = os.getenv("DATA_DIR")
if _data_dir_env:
    DATA_DIR = Path(_data_dir_env)
else:
    DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")

# Log the data directory (useful to confirm Railway Volume is mounted correctly)
print(f"[LOG] DATA_DIR configured as: {DATA_DIR.resolve()}")

# Ensure the directory exists on startup (safe to call multiple times)
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = "c!"

# PostgreSQL — Railway exposes DATABASE_URL (public) and DATABASE_PRIVATE_URL (internal).
# Accept either; reference one of them from the Postgres service in Railway Variables.
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PRIVATE_URL")

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

# Crew Booster perks panel (#crew-perks)
CREW_PERKS_CHANNEL_ID: int = 1521962377904525464
CREW_BOOSTER_ROLE_ID: int = 1503545672207438004
# Booster panel banner — wide image at the bottom of the embed (CREW_PERKS_BANNER_URL).
# Thumbnail always uses the server icon. CREW_PERKS_THUMBNAIL_URL is an optional banner fallback.
CREW_PERKS_THUMBNAIL_URL: str | None = os.getenv("CREW_PERKS_THUMBNAIL_URL")
CREW_PERKS_BANNER_URL: str | None = os.getenv("CREW_PERKS_BANNER_URL")

# Quill Tips panel (#tips or similar)
_raw_tips_channel = os.getenv("TIPS_CHANNEL_ID")
TIPS_CHANNEL_ID: int | None = int(_raw_tips_channel) if _raw_tips_channel else None
_raw_tips_review = os.getenv("TIPS_REVIEW_CHANNEL_ID")
TIPS_REVIEW_CHANNEL_ID: int | None = int(_raw_tips_review) if _raw_tips_review else None