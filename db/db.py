import asyncpg
import logging
from datetime import timezone
from config.config import DATABASE_URL

pool: asyncpg.Pool | None = None

async def init_pool():
    """
    Инициализирует пул подключений и создаёт нужные таблицы.
    """
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logging.info("Database pool initialized successfully.")
        async with pool.acquire() as conn:
            # Таблица сообщений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id      BIGINT       NOT NULL,
                    username     TEXT         NOT NULL,
                    text         TEXT         NOT NULL,
                    timestamp    TIMESTAMPTZ  NOT NULL
                );
            """)
            # Таблица настроек
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT         NOT NULL
                );
            """)
            # Таблица зарегистрированных чатов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id BIGINT PRIMARY KEY
                );
            """)
    except Exception as e:
        logging.error(f"❌ Database connection failed: {e}")
        raise

async def close_pool():
    """
    Закрывает пул подключений к БД.
    """
    global pool
    if pool:
        await pool.close()
        logging.info("🛑 Database pool closed successfully.")
        return

async def save_message(chat_id: int, username: str, text: str, timestamp):
    """
    Сохраняет сообщение в таблицу messages.
    """
    try:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages(chat_id, username, text, timestamp)
                VALUES($1, $2, $3, $4::timestamptz)
                """,
                chat_id, username, text, timestamp.isoformat()
            )
    except Exception as e:
        logging.error(f"❌ Error saving message: {e}")

async def register_chat(chat_id: int):
    """
    Регистрирует чат в таблице chats.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chats(chat_id) VALUES($1) ON CONFLICT DO NOTHING",
                chat_id
            )
    except Exception as e:
        logging.error(f"❌ Error registering chat: {e}")

async def get_registered_chats() -> list[int]:
    """
    Возвращает все chat_id из таблицы chats.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id FROM chats")
        return [r["chat_id"] for r in rows]
    except Exception as e:
        logging.error(f"❌ Error fetching registered chats: {e}")
        return []

async def get_chat_ids_for_summary(since=None) -> list[int]:
    """
    Возвращает список chat_id из messages с фильтром по дате.
    """
    try:
        async with pool.acquire() as conn:
            if since:
                rows = await conn.fetch(
                    "SELECT DISTINCT chat_id FROM messages WHERE timestamp >= $1",
                    since
                )
            else:
                rows = await conn.fetch("SELECT DISTINCT chat_id FROM messages")
        return [r["chat_id"] for r in rows]
    except Exception as e:
        logging.error(f"❌ Error fetching chat IDs for summary: {e}")
        return []

async def get_messages_for_summary(chat_id: int, since) -> list[dict]:
    """
    Возвращает сообщения за период по chat_id.
    """
    try:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT username, text, timestamp
                FROM messages
                WHERE chat_id = $1 AND timestamp >= $2
                ORDER BY timestamp ASC
                """,
                chat_id, since
            )
        return [
            {"username": r["username"], "text": r["text"], "timestamp": r["timestamp"]}
            for r in rows
        ]
    except Exception as e:
        logging.error(f"❌ Error fetching messages for summary: {e}")
        return []

async def get_setting(key: str) -> str | None:
    """
    Возвращает значение настройки по ключу.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else None
    except Exception as e:
        logging.error(f"❌ Error getting setting '{key}': {e}")
        return None

async def set_setting(key: str, value: str):
    """
    Устанавливает или обновляет значение настройки.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                key, value
            )
    except Exception as e:
        logging.error(f"❌ Error setting '{key}': {e}")
