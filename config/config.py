import os

def get_env_variable(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise OSError(f"Missing {name} in environment variables")
    return value

BOT_TOKEN = get_env_variable("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))
DATABASE_URL = get_env_variable("DATABASE_URL")
OPENROUTER_API_KEY = get_env_variable("OPENROUTER_API_KEY")

# 🔧 Добавь эти две переменные:
ADMIN_CHAT_ID = int(get_env_variable("ADMIN_CHAT_ID"))
RENDER_EXTERNAL_HOSTNAME = get_env_variable("RENDER_EXTERNAL_HOSTNAME")
