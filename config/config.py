# --- START OF config/config.py ---

import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла (важно для локальной разработки)
load_dotenv()

# --- Загрузка переменных из окружения ---

# Обязательные переменные (вызовут ошибку при запуске, если не найдены)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлена переменная окружения BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Не установлена переменная окружения DATABASE_URL")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("Не установлена переменная окружения OPENROUTER_API_KEY")

ADMIN_CHAT_ID_STR = os.getenv("ADMIN_CHAT_ID")
if not ADMIN_CHAT_ID_STR:
    raise ValueError("Не установлена переменная окружения ADMIN_CHAT_ID")
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)
except ValueError:
     raise ValueError(f"Некорректное значение ADMIN_CHAT_ID: '{ADMIN_CHAT_ID_STR}'. Должно быть число.")

# Переменные для вебхука (с значениями по умолчанию)
# WEBHOOK_HOST будет загружен, но его значение может быть не использовано, если есть RENDER_EXTERNAL_HOSTNAME
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "") # Загружаем, по умолчанию пустая строка
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook") # По умолчанию '/webhook'

# Порт (с значением по умолчанию)
try:
    PORT = int(os.getenv("PORT", 8000)) # По умолчанию 8000
except ValueError:
     raise ValueError(f"Некорректное значение PORT: '{os.getenv('PORT')}'. Должно быть число.")

# Переменную RENDER_EXTERNAL_HOSTNAME загружать здесь не нужно,
# так как main.py использует ее напрямую через os.getenv()

# --- Конец загрузки переменных ---

# Можно добавить здесь и другие настройки, не зависящие от окружения

# --- END OF config/config.py ---
