
import asyncpg
import logging
from config.config import DATABASE_URL

pool = None

async def init_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logging.info("Database pool initialized successfully.")
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise

async def close_pool():
    global pool
    if pool:
        await pool.close()
        logging.info("Database pool closed successfully.")

async def execute(query, *args):
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, *args)
    except Exception as e:
        logging.error(f"Failed to execute query: {e}")

async def fetch(query, *args):
    try:
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        return None
