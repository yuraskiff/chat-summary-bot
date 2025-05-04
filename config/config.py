# --- START OF FILE config/config.py ---

import os
import logging
from dotenv import load_dotenv

# Загружаем переменные из .env файла (важно для локальной разработки)
load_dotenv()

# --- Загрузка переменных из окружения ---
logging.info("Загрузка конфигурации из переменных окружения...")

# Обязательные переменные
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.critical("Не установлена переменная окружения BOT_TOKEN")
    raise ValueError("Не установлена переменная окружения BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.critical("Не установлена переменная окружения DATABASE_URL")
    raise ValueError("Не установлена переменная окружения DATABASE_URL")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logging.critical("Не установлена переменная окружения OPENROUTER_API_KEY")
    raise ValueError("Не установлена переменная окружения OPENROUTER_API_KEY")

ADMIN_CHAT_ID_STR = os.getenv("ADMIN_CHAT_ID")
if not ADMIN_CHAT_ID_STR:
    # Можно сделать ID админа необязательным, если нужно
    logging.warning("Не установлена переменная окружения ADMIN_CHAT_ID. Админ-команды не будут работать.")
    ADMIN_CHAT_ID = None # Устанавливаем None, если не задан
else:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)
    except ValueError:
        logging.critical(f"Некорректное значение ADMIN_CHAT_ID: '{ADMIN_CHAT_ID_STR}'. Должно быть число.")
        raise ValueError(f"Некорректное значение ADMIN_CHAT_ID: '{ADMIN_CHAT_ID_STR}'. Должно быть число.")

# Переменные для вебхука
# WEBHOOK_HOST может быть пустым, если используется RENDER_EXTERNAL_HOSTNAME
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")
if not WEBHOOK_PATH or not WEBHOOK_PATH.startswith("/"):
     logging.critical(f"Не установлена или некорректна переменная окружения WEBHOOK_PATH: '{WEBHOOK_PATH}'. Должна начинаться с '/'.")
     raise ValueError("Не установлена или некорректна переменная окружения WEBHOOK_PATH.")

# Порт
PORT_STR = os.getenv("PORT", "8000") # По умолчанию 8000
try:
    PORT = int(PORT_STR)
except ValueError:
     logging.critical(f"Некорректное значение PORT: '{PORT_STR}'. Должно быть число.")
     raise ValueError(f"Некорректное значение PORT: '{PORT_STR}'. Должно быть число.")

# Опциональный секрет вебхука
# WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

logging.info("Конфигурация успешно загружена.")
# --- END OF FILE config/config.py ---
