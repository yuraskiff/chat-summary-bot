import httpx
import logging

# Настройка логгера
logger = logging.getLogger(__name__)

# Название модели
MODEL = "openchat/openchat-3.5"

# URL OpenRouter API
API_URL = "https://openrouter.ai/api/v1/chat/completions"


async def summarize_chat(chat_history: list[str], api_key: str) -> str:
    """
    Отправляет чат в OpenRouter и возвращает саммари.
    :param chat_history: Список сообщений в чате
    :param api_key: API-ключ от OpenRouter
    :return: Строка-саммари
    """
    messages = [
        {"role": "system", "content": "Сделай краткое, весёлое и интересное саммари этого чата."},
    ] + [{"role": "user", "content": msg} for msg in chat_history]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://yourdomain.com",  # можно указать свой сайт, не обязательно
        "X-Title": "Chat Summary Bot"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter error: {e.response.status_code} - {e.response.text}")
        return "⚠️ Ошибка от OpenRouter API. Проверьте API-ключ и модель."
    except Exception as e:
        logger.exception("Ошибка при попытке получить саммари")
        return "⚠️ Ошибка при генерации саммари."
