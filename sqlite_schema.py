from __future__ import annotations

import logging
import sqlite3

from config import DATABASE_PATH, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    date TEXT NOT NULL,
    topic TEXT,
    subtopic TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    raw_file_path TEXT,
    embedding_status INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_hash TEXT,
    embedding_status INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, chunk_number),
    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_status ON chunks(embedding_status);
"""


def create_schema() -> None:
    ensure_dirs()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    logger.info("SQLite schema created at %s", DATABASE_PATH)


def main() -> None:
    create_schema()


if __name__ == "__main__":
    main()
