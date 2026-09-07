import json
import os
from datetime import datetime
from typing import Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_emails (
    id TEXT PRIMARY KEY,
    processed_at TIMESTAMP,
    category TEXT,
    is_newsletter BOOLEAN
);

CREATE TABLE IF NOT EXISTS extracted_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT,
    category TEXT,
    point TEXT,
    importance INTEGER,
    topic_tags TEXT,
    extracted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    timestamp TIMESTAMP
);
"""


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DB_PATH", "./pipeline.db")

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def is_processed(self, email_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM processed_emails WHERE id = ?", (email_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def mark_processed(
        self, email_id: str, category: str, is_newsletter: bool
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO processed_emails "
                "(id, processed_at, category, is_newsletter) VALUES (?, ?, ?, ?)",
                (email_id, datetime.utcnow().isoformat(), category, is_newsletter),
            )
            await db.commit()

    async def save_insight(
        self,
        email_id: str,
        category: str,
        point: str,
        importance: int,
        topic_tags: list[str],
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO extracted_insights "
                "(email_id, category, point, importance, topic_tags, extracted_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    email_id,
                    category,
                    point,
                    importance,
                    json.dumps(topic_tags),
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()

    async def log_usage(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO llm_usage "
                "(agent, model, input_tokens, output_tokens, cost_usd, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    agent,
                    model,
                    input_tokens,
                    output_tokens,
                    cost_usd,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
