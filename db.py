import asyncpg
import logging
from config import DATABASE_URL

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    logging.info("🌱 DB pool created")

async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        logging.info("🛑 DB pool closed")

async def save_message(chat_id: int, username: str, text: str, timestamp):
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (chat_id, username, text, timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                chat_id, username, text, timestamp
            )
    except Exception:
        logging.exception("❌ Error saving message to DB")

async def get_chat_ids_for_summary(since):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT chat_id FROM messages WHERE timestamp >= $1",
                since
            )
        return [r["chat_id"] for r in rows]
    except Exception:
        logging.exception("❌ Error fetching chat IDs from DB")
        return []

async def get_messages_for_summary(chat_id: int, since):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT username, text
                FROM messages
                WHERE chat_id = $1 AND timestamp >= $2
                ORDER BY timestamp ASC
                """,
                chat_id, since
            )
        return [{"username": r["username"], "text": r["text"]} for r in rows]
    except Exception:
        logging.exception("❌ Error fetching messages from DB")
        return []
