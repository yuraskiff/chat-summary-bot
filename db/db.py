# --- START OF FILE db.py ---

import asyncpg
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Union # Используем typing

# Импортируем URL из правильного места
from config.config import DATABASE_URL

# Определяем тип пула для подсказок
PoolType = Optional[asyncpg.Pool]
pool: PoolType = None

async def init_pool():
    """Инициализирует пул соединений с БД и создает таблицы/индексы, если их нет."""
    global pool
    if pool:
        logging.warning("Пул БД уже инициализирован.")
        return
    try:
        logging.info(f"Подключение к БД: {DATABASE_URL.split('@')[-1]}") # Лог без пароля
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        logging.info("Пул соединений с БД успешно инициализирован.")

        async with pool.acquire() as conn:
            logging.info("Проверка и создание таблиц...")
            # Таблица сообщений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_internal_id SERIAL PRIMARY KEY, -- Добавим автоинкрементный ID для удобства
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
                    value TEXT NOT NULL
                );
            """)
            # Таблица зарегистрированных чатов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id BIGINT PRIMARY KEY
                );
            """)
            logging.info("Таблицы проверены/созданы.")

            # Создание индексов для ускорения выборок
            logging.info("Проверка и создание индексов...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_chat_id_timestamp ON messages (chat_id, timestamp DESC);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp DESC);
            """)
            logging.info("Индексы проверены/созданы.")

    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при инициализации БД: {e}")
        pool = None # Сбрасываем пул при ошибке
        raise # Передаем исключение выше

async def close_pool():
    """Закрывает пул соединений с БД."""
    global pool
    if pool:
        try:
            await pool.close()
            logging.info("🛑 Пул соединений с БД успешно закрыт.")
        except Exception as e:
            logging.exception(f"❌ Ошибка при закрытии пула БД: {e}")
        finally:
            pool = None
    else:
        logging.warning("Попытка закрыть неинициализированный пул БД.")


async def _get_connection():
    """Вспомогательная функция для получения соединения из пула."""
    if not pool:
        logging.error("Пул БД не инициализирован!")
        raise ConnectionError("Database pool is not initialized")
    return await pool.acquire()

async def _release_connection(conn, exc=None):
    """Вспомогательная функция для возвращения соединения в пул."""
    if pool and conn:
        await pool.release(conn, timeout=5) # Даем 5 секунд на возврат


async def save_message(chat_id: int, username: str, text: str, timestamp: datetime):
    """Сохраняет сообщение, гарантируя, что timestamp сохраняется как aware UTC."""
    conn = None
    try:
        conn = await _get_connection()
        # Убеждаемся, что время aware и в UTC перед сохранением
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        elif timestamp.tzinfo != timezone.utc:
            timestamp = timestamp.astimezone(timezone.utc)

        await conn.execute(
            """
            INSERT INTO messages(chat_id, username, text, "timestamp")
            VALUES($1, $2, $3, $4)
            """,
            chat_id, username, text, timestamp
        )
        # Убрали отладочный лог отсюда, чтобы не засорять вывод
    except Exception as e:
        logging.exception(f"❌ Ошибка при сохранении сообщения в чате {chat_id}: {e}")
    finally:
        if conn: await _release_connection(conn)


async def register_chat(chat_id: int):
    """Регистрирует чат для последующей обработки."""
    conn = None
    try:
        conn = await _get_connection()
        result = await conn.execute(
            "INSERT INTO chats(chat_id) VALUES($1) ON CONFLICT(chat_id) DO NOTHING",
            chat_id
        )
        # INSERT 0 1 означает, что строка была успешно вставлена
        if result == "INSERT 0 1":
            logging.info(f"Чат {chat_id} успешно зарегистрирован.")
        # Если конфликт (чат уже есть), result может быть другим или не быть,
        # в любом случае это не ошибка.
    except Exception as e:
        logging.exception(f"❌ Ошибка при регистрации чата {chat_id}: {e}")
    finally:
        if conn: await _release_connection(conn)


async def get_registered_chats() -> List[int]:
    """Получает список ID всех зарегистрированных чатов."""
    conn = None
    try:
        conn = await _get_connection()
        rows = await conn.fetch("SELECT chat_id FROM chats")
        return [r["chat_id"] for r in rows]
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении списка зарегистрированных чатов: {e}")
        return [] # Возвращаем пустой список при ошибке
    finally:
        if conn: await _release_connection(conn)


async def get_messages_for_summary(chat_id: int, since: datetime) -> List[Dict]:
    """Получает сообщения для саммари из указанного чата с указанного времени (aware UTC)."""
    conn = None
    messages = []
    try:
        conn = await _get_connection()
        # Убеждаемся, что since - aware UTC
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        elif since.tzinfo != timezone.utc:
            since = since.astimezone(timezone.utc)

        # Используем индекс idx_messages_chat_id_timestamp
        rows = await conn.fetch(
            """
            SELECT username, text, "timestamp"
            FROM messages
            WHERE chat_id = $1 AND "timestamp" >= $2
            ORDER BY "timestamp" ASC
            """,
            chat_id, since
        )
        # asyncpg возвращает timestamp как aware datetime (обычно UTC для TIMESTAMPTZ)
        messages = [
            {"username": r["username"], "text": r["text"], "timestamp": r["timestamp"]}
            for r in rows
        ]
    except Exception as e:
        # Логируем конкретную ошибку при выборке
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id} с {since}: {e}")
    finally:
        if conn: await _release_connection(conn)
    return messages


async def get_setting(key: str) -> Optional[str]:
    """Получает значение настройки по ключу."""
    conn = None
    try:
        conn = await _get_connection()
        # Используем fetchval для получения одного значения или None
        value = await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
        return value
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении настройки '{key}': {e}")
        return None # Возвращаем None при ошибке
    finally:
        if conn: await _release_connection(conn)


async def set_setting(key: str, value: str):
    """Устанавливает или обновляет значение настройки."""
    conn = None
    try:
        conn = await _get_connection()
        await conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            key, value
        )
    except Exception as e:
        logging.exception(f"❌ Ошибка при установке настройки '{key}': {e}")
    finally:
        if conn: await _release_connection(conn)

# --- END OF FILE db.py ---
