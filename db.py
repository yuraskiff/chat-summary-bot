import asyncpg
from config import DATABASE_URL

async def save_message(username: str, text: str, timestamp):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO messages (username, text, timestamp) VALUES ($1, $2, $3)",
        username, text, timestamp
    )
    await conn.close()

async def get_messages_for_summary(since):
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        "SELECT username, text FROM messages WHERE timestamp >= $1 ORDER BY timestamp ASC",
        since
    )
    await conn.close()
    return [{"username": row["username"], "text": row["text"]} for row in rows]
