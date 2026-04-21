from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_ROOT = BASE_DIR / "raw" / "setopati"
PROCESSED_ROOT = BASE_DIR / "processed"
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "news.db"

SOURCE_NAME = "setopati"
SOURCE_URL = "https://www.setopati.com"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "20"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
MIN_CONTENT_CHARS = int(os.getenv("MIN_CONTENT_CHARS", "500"))
CHUNK_WORD_SIZE = int(os.getenv("CHUNK_WORD_SIZE", "500"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

ADS_KEYWORDS = {
    "ad",
    "ads",
    "advert",
    "sponsor",
    "promo",
    "share",
    "follow",
    "newsletter",
    "cookie",
    "related",
    "trending",
    "social",
}

TOPIC_FALLBACK = "uncategorized"
SUBTOPIC_FALLBACK = "general"


def ensure_dirs() -> None:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
