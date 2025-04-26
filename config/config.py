
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_env_variable(var_name):
    value = os.getenv(var_name)
    if not value:
        logging.error(f"Environment variable '{var_name}' not set.")
        raise EnvironmentError(f"Missing {var_name} in environment variables")
    return value

BOT_TOKEN = get_env_variable('BOT_TOKEN')
DATABASE_URL = get_env_variable('DATABASE_URL')
OPENROUTER_API_KEY = get_env_variable('OPENROUTER_API_KEY')
