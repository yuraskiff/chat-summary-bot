import httpx
import logging
import textwrap
from config.config import OPENROUTER_API_KEY

MODEL = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://api.openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "HTTP-Referer": "https://chat-summary-bot.onrender.com",
    "X-Title": "chat-summary-bot",
    "Content-Type": "application/json",
}

async def summarize_chat(chat_history: list[str], user_prompt: str | None = None) -> str | None:
    """
    Собирает историю чата и отправляет её на модель DeepSeek.
    Возвращает текст сводки или None при ошибке.
    """
    system_msg = "Ты — помощник для анализа чатов."
    default_prompt = textwrap.dedent("""
        Собери сообщения за последние 24 часа и сделай заключение, которое состоит из:
        – Темы обсуждений
        – Кто был полезен/бесполезен и почему
        – Плюсы и минусы беседы
        – Кто чаще всех писал
        – Психологический портрет участников
        – Предложение новой темы
        – Короткая шутка на тему беседы
    """).strip()
    prompt = user_prompt or default_prompt

    messages = [{"role": "system", "content": system_msg}]
    messages += [{"role": "user", "content": prompt}]
    messages += [{"role": "user", "content": block} for block in chat_history]

    logging.info("📤 Отправляем %d блоков в OpenRouter", len(chat_history))

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(API_URL, headers=HEADERS, json={
                "model": MODEL,
                "messages": messages,
            })
            response.raise_for_status()
            data = response.json()
            logging.info("✅ Получен ответ от модели")
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error("❌ Ошибка при запросе к OpenRouter: %s", e)
        return None
