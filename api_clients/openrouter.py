import httpx
import logging
from config.config import OPENROUTER_API_KEY

# Модель DeepSeek-Chat-V3-0324 (free) в OpenRouter
MODEL   = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://api.openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

async def request_openrouter(messages: list[dict]) -> dict | None:
    """
    Отправляет на OpenRouter чат-сообщения в формате:
      [{"role": "system", "content": "..."},
       {"role": "user",   "content": "..."}]
    и возвращает JSON-ответ.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logging.error(f"Openrouter request error: {e}")
        return None
