import httpx
import logging
import textwrap

from config.config import OPENROUTER_API_KEY

# Модель и URL API
MODEL = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://api.openrouter.ai/api/v1/chat/completions"
# Таймауты: connect=10s, read=60s
TIMEOUT = httpx.Timeout(10.0, read=60.0)


async def summarize_chat(blocks: list[str], prompt: str) -> str | None:
    """
    Отправляет в OpenRouter промпт + список блоков сообщений, возвращает текст сводки или None.
    """

    # Логируем исходные данные
    logging.info("▶ Summarization prompt:\n%s", textwrap.indent(prompt, "  "))
    logging.info("▶ Number of blocks: %d", len(blocks))

    # Готовим полезную нагрузку
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": prompt}]
        + [{"role": "user", "content": block} for block in blocks],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    try:
        # Отправляем запрос
        logging.info("🔄 Sending request to OpenRouter at %s", API_URL)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(API_URL, headers=headers, json=payload)

        logging.info("🔔 Response status code: %d", response.status_code)
        data = response.json()
        logging.info("🔍 Received JSON keys: %s", list(data.keys()))

        # Проверяем структуру ответа
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            logging.error("❌ Unexpected or empty 'choices' in response: %s", data)
            return None

        message = choices[0].get("message")
        if not isinstance(message, dict):
            logging.error("❌ Missing 'message' in first choice: %s", choices[0])
            return None

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            logging.error("❌ Empty or invalid 'content' in message: %s", message)
            return None

        logging.info("✅ Summarization successful, length=%d characters", len(content))
        return content

    except Exception as e:
        logging.exception("❌ Exception in summarize_chat: %s", e)
        return None
