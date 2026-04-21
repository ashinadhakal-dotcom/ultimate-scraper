from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from pathlib import Path

import google.generativeai as genai

from config import (
    CHUNK_WORD_SIZE,
    DATABASE_PATH,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PROCESSED_ROOT,
    SUBTOPIC_FALLBACK,
    TOPIC_FALLBACK,
    ensure_dirs,
)
from sqlite_schema import create_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _article_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunks(content: str, words_per_chunk: int) -> list[str]:
    words = content.split()
    if not words:
        return []
    return [" ".join(words[i : i + words_per_chunk]).strip() for i in range(0, len(words), words_per_chunk)]


def _classify(content: str) -> tuple[str, str]:
    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        return TOPIC_FALLBACK, SUBTOPIC_FALLBACK

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", GEMINI_MODEL))
        prompt = (
            "Classify Nepali news text into topic and subtopic. "
            "Return strict JSON with keys topic and subtopic only.\n"
            f"TEXT:\n{content[:4000]}"
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return TOPIC_FALLBACK, SUBTOPIC_FALLBACK
        parsed = json.loads(text[start : end + 1])
        topic = str(parsed.get("topic") or TOPIC_FALLBACK).strip()
        subtopic = str(parsed.get("subtopic") or SUBTOPIC_FALLBACK).strip()
        return topic, subtopic
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini classification failed: %s", exc)
        return TOPIC_FALLBACK, SUBTOPIC_FALLBACK


def insert_processed() -> int:
    _load_dotenv()
    ensure_dirs()
    create_schema()

    processed_files = sorted(PROCESSED_ROOT.glob("*/*/*/article_*_processed.json"))
    logger.info("Found %d processed files", len(processed_files))

    inserted = 0
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("PRAGMA foreign_keys=ON")

        for file_path in processed_files:
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                url = (payload.get("url") or "").strip()
                content = (payload.get("cleaned_content") or "").strip()
                if not url or not content:
                    continue

                article_hash = _article_hash(url)
                exists = conn.execute(
                    "SELECT id FROM articles WHERE article_hash = ?",
                    (article_hash,),
                ).fetchone()
                if exists:
                    continue

                topic, subtopic = _classify(content)
                cursor = conn.execute(
                    """
                    INSERT INTO articles (
                        article_hash, source, date, topic, subtopic,
                        title, content, url, raw_file_path, embedding_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        article_hash,
                        payload.get("source", "setopati"),
                        payload.get("date", ""),
                        topic,
                        subtopic,
                        (payload.get("title") or "").strip() or "Untitled",
                        content,
                        url,
                        payload.get("raw_file_path", ""),
                    ),
                )
                article_id = cursor.lastrowid

                chunks = _chunks(content, CHUNK_WORD_SIZE)
                chunk_rows = [
                    (article_id, idx + 1, chunk, _chunk_hash(chunk), 0)
                    for idx, chunk in enumerate(chunks)
                    if chunk
                ]
                if chunk_rows:
                    conn.executemany(
                        """
                        INSERT INTO chunks (
                            article_id, chunk_number, chunk_text, chunk_hash, embedding_status
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        chunk_rows,
                    )

                inserted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Insert failed for %s: %s", file_path, exc)

        conn.commit()

    logger.info("Inserted %d new articles", inserted)
    return inserted


def main() -> None:
    insert_processed()


if __name__ == "__main__":
    main()
