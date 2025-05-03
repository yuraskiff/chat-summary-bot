import os
import logging
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Базовая настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_env_variable(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        logging.error(f"Environment variable '{var_name}' not set.")
        raise EnvironmentError(f"Missing {var_name} in environment variables")
    return value

BOT_TOKEN         = get_env_variable('BOT_TOKEN')
DATABASE_URL      = get_env_variable('DATABASE_URL')
OPENROUTER_API_KEY= get_env_variable('OPENROUTER_API_KEY')
ADMIN_CHAT_ID     = int(get_env_variable('ADMIN_CHAT_ID'))
