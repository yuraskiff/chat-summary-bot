import httpx
import logging

logger = logging.getLogger(__name__)

MODEL = "meta-llama/llama-3.1-8b-instruct:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def summarize_chat(chat_history: list[str], api_key: str) -> str:
    messages = [{"role": "user", "content": "\n".join(chat_history)}]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": messages
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(API_URL, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        logger.error(f"Ошибка OpenRouter: {response.status_code} - {response.text}")
        raise Exception("Ошибка при обращении к OpenRouter API")
