import os
from dotenv import load_dotenv

load_dotenv()

# Проверяем обязательные переменные окружения
REQUIRED = ["TELEGRAM_TOKEN", "OPENROUTER_API_KEY", "DATABASE_URL", "ADMIN_CHAT_ID"]
missing = [v for v in REQUIRED if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Отсутствуют обязательные переменные: {', '.join(missing)}")

TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATABASE_URL       = os.getenv("DATABASE_URL")
ADMIN_CHAT_ID      = int(os.getenv("ADMIN_CHAT_ID"))
