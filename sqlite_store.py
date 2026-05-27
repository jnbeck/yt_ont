"""
SQLite storage layer for raw and enriched comments.

Tables:
  raw_comments      - comments exactly as fetched from YouTube
  enriched_comments - Claude classifications linked by comment_id
  questions         - questions extracted from substantive comments
  claims            - claims extracted from substantive comments
  extraction_log    - tracks which comments have been through deep extraction
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_comments (
                comment_id        TEXT PRIMARY KEY,
                video_id          TEXT NOT NULL,
                video_title       TEXT,
                parent_id         TEXT,
                text              TEXT NOT NULL,
                author_channel_id TEXT,
                like_count        INTEGER DEFAULT 0,
                published_at      TEXT,
                reply_count       INTEGER DEFAULT 0,
                inserted_at       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS enriched_comments (
                comment_id       TEXT PRIMARY KEY,
                stance           TEXT,
                theological_tone TEXT,
                is_substantive   INTEGER,
                topics           TEXT,
                confidence       REAL,
                one_line_reason  TEXT,
                model_version    TEXT,
                processed_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS questions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id   TEXT NOT NULL,
                video_id     TEXT NOT NULL,
                text         TEXT NOT NULL,
                is_implied   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS claims (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id   TEXT NOT NULL,
                video_id     TEXT NOT NULL,
                text         TEXT NOT NULL,
                claim_type   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extraction_log (
                comment_id     TEXT PRIMARY KEY,
                model_version  TEXT,
                processed_at   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_raw_video_id ON raw_comments(video_id);
            CREATE INDEX IF NOT EXISTS idx_enriched_stance ON enriched_comments(stance);
            CREATE INDEX IF NOT EXISTS idx_questions_video ON questions(video_id);
            CREATE INDEX IF NOT EXISTS idx_claims_video ON claims(video_id);
        """)


def insert_raw_comments(db_path: str, comments: list[dict], video_title: str = "") -> int:
    """Insert comments, skipping any that already exist. Returns count of new rows."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with get_conn(db_path) as conn:
        for c in comments:
            result = conn.execute(
                """INSERT OR IGNORE INTO raw_comments
                   (comment_id, video_id, video_title, parent_id, text,
                    author_channel_id, like_count, published_at, reply_count, inserted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    c["comment_id"], c["video_id"], video_title,
                    c.get("parent_id"), c["text"],
                    c.get("author_channel_id"), c.get("like_count", 0),
                    c.get("published_at"), c.get("reply_count", 0), now,
                ),
            )
            inserted += result.rowcount
    return inserted


def get_unprocessed_comments(db_path: str) -> list[dict]:
    """Return raw comments that have no enriched record yet."""
    with get_conn(db_path) as conn:
        rows = conn.execute("""
            SELECT r.comment_id, r.text
            FROM raw_comments r
            LEFT JOIN enriched_comments e ON r.comment_id = e.comment_id
            WHERE e.comment_id IS NULL
        """).fetchall()
    return [dict(row) for row in rows]


def get_unextracted_comments(db_path: str) -> list[dict]:
    """Return substantive comments that have not yet been through deep extraction."""
    with get_conn(db_path) as conn:
        rows = conn.execute("""
            SELECT r.comment_id, r.video_id, r.text, r.like_count,
                   e.stance, e.theological_tone
            FROM raw_comments r
            JOIN enriched_comments e ON r.comment_id = e.comment_id
            LEFT JOIN extraction_log x ON r.comment_id = x.comment_id
            WHERE e.is_substantive = 1
              AND x.comment_id IS NULL
        """).fetchall()
    return [dict(row) for row in rows]


def insert_extraction(db_path: str, comment_id: str, video_id: str,
                      questions: list[dict], claims: list[dict], model_version: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn(db_path) as conn:
        for q in questions:
            conn.execute(
                "INSERT INTO questions (comment_id, video_id, text, is_implied) VALUES (?, ?, ?, ?)",
                (comment_id, video_id, q["text"], 1 if q.get("is_implied") else 0),
            )
        for c in claims:
            conn.execute(
                "INSERT INTO claims (comment_id, video_id, text, claim_type) VALUES (?, ?, ?, ?)",
                (comment_id, video_id, c["text"], c.get("claim_type", "neutral")),
            )
        conn.execute(
            "INSERT OR REPLACE INTO extraction_log (comment_id, model_version, processed_at) VALUES (?, ?, ?)",
            (comment_id, model_version, now),
        )


def insert_enriched_comment(db_path: str, comment_id: str, result: dict, model_version: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO enriched_comments
               (comment_id, stance, theological_tone, is_substantive,
                topics, confidence, one_line_reason, model_version, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                comment_id,
                result.get("stance"),
                result.get("theological_tone"),
                1 if result.get("is_substantive") else 0,
                json.dumps(result.get("topics", [])),
                result.get("confidence"),
                result.get("one_line_reason"),
                model_version,
                now,
            ),
        )