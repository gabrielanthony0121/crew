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