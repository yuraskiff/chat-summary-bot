import httpx
import logging
from config.config import OPENROUTER_API_KEY

MODEL   = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://api.openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

async def request_openrouter(messages: list[dict]) -> dict | None:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"model": MODEL, "messages": messages}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logging.error(f"Openrouter request error: {e}")
        return None

async def generate_summary(messages: list[str], summary_type: str) -> str | None:
    system_prompt = (
        "Ты — аналитик групповых чатов. На основе следующих сообщений за последние 24 часа сформируй:\n"
        "– Темы обсуждения\n"
        "– Полезные собеседники и почему\n"
        "– Бесполезные собеседники и почему\n"
        "– Хорошие и плохие стороны беседы\n"
        "– Самые активные участники\n"
        "– Психологический портрет участников\n"
        "– Предложение новой темы\n"
        f"Тип суммаризации: {summary_type}\n"
        "Используй свободный разговорный стиль."
    )
    msgs = [{"role": "system", "content": system_prompt}] + [
        {"role": "user", "content": m} for m in messages
    ]
    resp = await request_openrouter(msgs)
    if resp and "choices" in resp:
        return resp["choices"][0]["message"]["content"]
    return None
