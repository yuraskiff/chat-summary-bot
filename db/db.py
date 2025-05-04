# --- START OF FILE db.py ---

import asyncpg
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional # Используем typing для подсказок

# Импортируем URL из конфигурации
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
        # Логируем хост БД без учетных данных для безопасности
        db_host_info = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL
        logging.info(f"Подключение к БД: {db_host_info}")
        # Создаем пул соединений
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, command_timeout=60)
        if not pool:
             # Эта проверка на случай, если create_pool вернет None (хотя обычно вызывает исключение)
             logging.critical("Не удалось создать пул соединений с БД (pool is None).")
             raise ConnectionError("Failed to create database pool")
        logging.info("Пул соединений с БД успешно инициализирован.")

        # Получаем соединение для проверки/создания таблиц
        async with pool.acquire() as conn:
            logging.info("Проверка и создание таблиц...")
            # Таблица сообщений
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_internal_id SERIAL PRIMARY KEY, -- Внутренний ID сообщения
                    chat_id      BIGINT       NOT NULL,
                    username     TEXT         NOT NULL,
                    text         TEXT         NOT NULL,
                    "timestamp"  TIMESTAMPTZ  NOT NULL     -- Используем кавычки, т.к. timestamp - ключевое слово
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
            # Индекс для выборки сообщений по чату и времени (важен для сводок)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_chat_id_timestamp ON messages (chat_id, "timestamp" DESC);
            """)
            # Индекс для выборки по времени (может быть полезен)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages ("timestamp" DESC);
            """)
            logging.info("Индексы проверены/созданы.")

    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при инициализации БД: {e}")
        pool = None # Сбрасываем пул при ошибке
        raise # Передаем исключение выше, чтобы остановить запуск приложения

async def close_pool():
    """Закрывает пул соединений с БД."""
    global pool
    if pool:
        logging.info("Закрытие пула соединений с БД...")
        try:
            await pool.close()
            logging.info("🛑 Пул соединений с БД успешно закрыт.")
        except Exception as e:
            logging.exception(f"❌ Ошибка при закрытии пула БД: {e}")
        finally:
            pool = None # Гарантированно сбрасываем пул
    else:
        logging.warning("Попытка закрыть неинициализированный или уже закрытый пул БД.")


async def _get_connection() -> asyncpg.Connection:
    """Вспомогательная функция для получения соединения из пула с проверкой."""
    if not pool:
        logging.error("Пул БД не инициализирован! Невозможно получить соединение.")
        raise ConnectionError("Database pool is not initialized or already closed")
    try:
        # Получаем соединение с таймаутом, чтобы не ждать вечно
        conn = await pool.acquire(timeout=10)
        if not conn:
             raise ConnectionError("Failed to acquire connection from pool (timeout or pool closed)")
        return conn
    except Exception as e:
        logging.exception("Не удалось получить соединение из пула БД.")
        raise ConnectionError("Failed to acquire connection from pool") from e

async def _release_connection(conn: asyncpg.Connection):
    """Вспомогательная функция для безопасного возвращения соединения в пул."""
    if pool and conn and not conn.is_closed():
        try:
            # Возвращаем соединение в пул
            await pool.release(conn, timeout=5)
        except Exception as e:
            logging.exception(f"Ошибка при возврате соединения в пул: {e}")
            # Если не удалось вернуть, пытаемся закрыть соединение
            try:
                await conn.close()
            except Exception as close_exc:
                 logging.exception(f"Ошибка при принудительном закрытии соединения: {close_exc}")
    elif not pool:
         logging.warning("Попытка вернуть соединение при неинициализированном пуле.")


async def save_message(chat_id: int, username: str, text: str, timestamp: datetime):
    """Сохраняет сообщение, гарантируя, что timestamp сохраняется как aware UTC."""
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _get_connection()
        # Убеждаемся, что время aware и в UTC перед сохранением
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        elif timestamp.tzinfo != timezone.utc:
            timestamp = timestamp.astimezone(timezone.utc)

        # Используем кавычки для "timestamp", т.к. это ключевое слово в SQL
        await conn.execute(
            """
            INSERT INTO messages(chat_id, username, text, "timestamp")
            VALUES($1, $2, $3, $4)
            """,
            chat_id, username, text, timestamp
        )
    except Exception as e:
        # Логируем исключение с traceback
        logging.exception(f"❌ Ошибка при сохранении сообщения в чате {chat_id}: {e}")
    finally:
        if conn: await _release_connection(conn)


async def register_chat(chat_id: int):
    """Регистрирует чат для последующей обработки."""
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _get_connection()
        result = await conn.execute(
            "INSERT INTO chats(chat_id) VALUES($1) ON CONFLICT(chat_id) DO NOTHING",
            chat_id
        )
        # Проверяем результат команды INSERT
        if result == "INSERT 0 1":
            logging.info(f"Чат {chat_id} успешно зарегистрирован.")
        # Если был конфликт (чат уже есть), лог не нужен.
    except Exception as e:
        logging.exception(f"❌ Ошибка при регистрации чата {chat_id}: {e}")
    finally:
        if conn: await _release_connection(conn)


async def get_registered_chats() -> List[int]:
    """Получает список ID всех зарегистрированных чатов."""
    conn: Optional[asyncpg.Connection] = None
    chats = []
    try:
        conn = await _get_connection()
        rows = await conn.fetch("SELECT chat_id FROM chats")
        chats = [r["chat_id"] for r in rows]
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении списка зарегистрированных чатов: {e}")
        # Возвращаем пустой список при ошибке
    finally:
        if conn: await _release_connection(conn)
    return chats


async def get_messages_for_summary(chat_id: int, since: datetime) -> List[Dict]:
    """Получает сообщения для саммари из указанного чата с указанного времени (aware UTC)."""
    conn: Optional[asyncpg.Connection] = None
    messages = []
    try:
        conn = await _get_connection()
        # Убеждаемся, что `since` - aware UTC перед передачей в запрос
        if since.tzinfo is None:
            logging.warning(f"Получено naive datetime ({since}) в get_messages_for_summary, преобразуем в UTC.")
            since = since.replace(tzinfo=timezone.utc)
        elif since.tzinfo != timezone.utc:
            logging.warning(f"Получено non-UTC aware datetime ({since.tzinfo}) в get_messages_for_summary, преобразуем в UTC.")
            since = since.astimezone(timezone.utc)

        # ----> КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: ДОБАВЛЕНО ::TIMESTAMPTZ <----
        # Явно приводим тип параметра $2 к TIMESTAMPTZ для PostgreSQL
        rows = await conn.fetch(
            """
            SELECT username, text, "timestamp"
            FROM messages
            WHERE chat_id = $1 AND "timestamp" >= $2::TIMESTAMPTZ
            ORDER BY "timestamp" ASC
            """,
            chat_id, since # Передаем уже подготовленный aware UTC datetime
        )
        # asyncpg корректно декодирует TIMESTAMPTZ из БД в aware datetime (UTC)
        messages = [
            {"username": r["username"], "text": r["text"], "timestamp": r["timestamp"]}
            for r in rows
        ]
    except asyncpg.exceptions.DataError as de:
         # Ловим конкретную ошибку данных, если она все еще возникает (маловероятно теперь)
         logging.exception(f"❌ Ошибка данных asyncpg при получении сообщений для сводки чата {chat_id} с {since}: {de}. Аргумент $2: {since} (tz={since.tzinfo})")
         logging.error(f"Тип аргумента 'since': {type(since)}")
    except Exception as e:
        # Логируем другие возможные ошибки
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id} с {since}: {e}")
    finally:
        if conn: await _release_connection(conn)
    return messages # Возвращаем пустой список в случае ошибки


async def get_setting(key: str) -> Optional[str]:
    """Получает значение настройки по ключу."""
    conn: Optional[asyncpg.Connection] = None
    value = None
    try:
        conn = await _get_connection()
        # Используем fetchval для получения одного значения или None
        value = await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении настройки '{key}': {e}")
    finally:
        if conn: await _release_connection(conn)
    return value # Возвращает None, если ключ не найден или произошла ошибка


async def set_setting(key: str, value: str):
    """Устанавливает или обновляет значение настройки."""
    conn: Optional[asyncpg.Connection] = None
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
        # Возможно, стоит перевыбросить исключение, если это критично
        # raise e
    finally:
        if conn: await _release_connection(conn)

# --- END OF FILE db.py ---
