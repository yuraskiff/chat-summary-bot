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
    sql = [
        """
        CREATE TABLE IF NOT EXISTS chats (
            chat_id BIGINT PRIMARY KEY
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT REFERENCES chats(chat_id),
            user_id BIGINT,
            user_name TEXT,
            content TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    ]
    async with pool.acquire() as conn:
        for q in sql:
            await conn.execute(q)

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
