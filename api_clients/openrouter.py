import httpx
import logging
from config.config import OPENROUTER_API_KEY

# Модель DeepSeek-Chat-V3-0324 (free) в OpenRouter
MODEL   = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://api.openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

async def summarize_chat(chat_history: list[str], user_prompt: str | None = None) -> str | None:
    """
    Собирает историю чата и отправляет её на модель DeepSeek.
    Возвращает текст сводки или None при ошибке.
    """
    system_msg = "Ты — помощник для анализа чатов."
    default_prompt = (
        "Собери сообщения за последние 24 часа и сделай заключение, которое состоит из:\n"
        "- Темы обсуждений\n"
        "- Кто был полезен/бесполезен и почему\n"
        "- Плюсы и минусы беседы\n"
        "- Кто чаще всех писал\n"
        "- Психологический портрет участников\n"
        "- Предложение новой темы\n"
        "- Короткая шутка на тему беседы\n"
    )
    prompt = user_prompt or default_prompt
    chat_text = "\n".join(chat_history)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": f"{prompt}\n\n{chat_text}"}
    ]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(API_URL, json={"model": MODEL, "messages": messages}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        logging.error(f"Openrouter request error: {e}")
        return None
