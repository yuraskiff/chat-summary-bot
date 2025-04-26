import asyncpg
import logging
from config import DATABASE_URL

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    logging.info("🌱 DB pool created")
    # создаём таблицы, если их нет
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                chat_id BIGINT NOT NULL,
                username TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        logging.info("🛑 DB pool closed")

async def save_message(chat_id: int, username: str, text: str, timestamp):
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages(chat_id, username, text, timestamp) VALUES($1,$2,$3,$4)",
                chat_id, username, text, timestamp
            )
    except Exception:
        logging.exception("❌ Error saving message")

async def get_chat_ids_for_summary(since=None):
    try:
        async with pool.acquire() as conn:
            if since:
                rows = await conn.fetch(
                    "SELECT DISTINCT chat_id FROM messages WHERE timestamp >= $1", since
                )
            else:
                rows = await conn.fetch("SELECT DISTINCT chat_id FROM messages")
        return [r["chat_id"] for r in rows]
    except Exception:
        logging.exception("❌ Error fetching chat IDs")
        return []

async def get_messages_for_summary(chat_id: int, since):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT username, text, timestamp FROM messages
                 WHERE chat_id = $1 AND timestamp >= $2
                 ORDER BY timestamp ASC",
                chat_id, since
            )
        return [{"username": r["username"], "text": r["text"], "timestamp": r["timestamp"]} for r in rows]
    except Exception:
        logging.exception("❌ Error fetching messages")
        return []

async def get_setting(key: str, default=None):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
    return row["value"] if row else default

async def set_setting(key: str, value: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            key, value
        )
