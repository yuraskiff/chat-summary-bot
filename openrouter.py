import httpx
import logging
from config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

MODEL = "meta-llama/llama-3.1-8b-instruct:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def summarize_chat(chat_history: list[str]) -> str:
    messages = [{"role": "user", "content": "\n".join(chat_history)}]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": messages
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Ошибка от OpenRouter: {e}")
        return "⚠️ Ошибка от OpenRouter API. Проверьте API-ключ и модель."
