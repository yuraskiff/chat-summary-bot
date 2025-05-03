import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_env_variable(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        logging.error(f"Environment variable '{var_name}' not set.")
        raise EnvironmentError(f"Missing {var_name} in environment variables")
    return value

# Telegram bot token
BOT_TOKEN = get_env_variable('BOT_TOKEN')
# URL для webhook, например: https://your-service.onrender.com/webhook/<BOT_TOKEN>
WEBHOOK_URL = get_env_variable('WEBHOOK_URL')
# Порт для aiohttp (Render автоматически передаёт PORT)
PORT = int(os.getenv('PORT', '8000'))
# URL подключения к базе данных
DATABASE_URL = get_env_variable('DATABASE_URL')
# Ключ для OpenRouter
OPENROUTER_API_KEY = get_env_variable('OPENROUTER_API_KEY')
# ID администратора (целое число)
ADMIN_CHAT_ID = int(get_env_variable('ADMIN_CHAT_ID'))
