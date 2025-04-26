import asyncpg
import logging
from config.config import DATABASE_URL

pool = None

async def init_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logging.info("Database pool initialized successfully.")
        await _create_tables()
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise

async def close_pool():
    global pool
    if pool:
        await pool.close()
        logging.info("Database pool closed successfully.")

async def _create_tables():
    async with pool.acquire() as conn:
        # создаём таблицы, если отсутствуют
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id BIGINT PRIMARY KEY
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            user_name TEXT,
            content TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        # миграция: добавляем chat_id в сообщения, если его нет
        await conn.execute("""
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS chat_id BIGINT
        REFERENCES chats(chat_id);
        """)

async def execute(query: str, *args):
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, *args)
    except Exception as e:
        logging.error(f"Failed to execute query: {e}")

async def fetch(query: str, *args):
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        return None
