import httpx
import os
from config import OPENROUTER_API_KEY

MODEL = "meta-llama/llama-3.1-8b-instruct:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def summarize_chat(chat_history: list[str]) -> str:
    prompt = (
        "Собери сообщения за последние 24 часа и сделай заключение, которое состоит из следующей информации:\n\n"
        "- Какие темы обсуждались\n"
        "- Какие собеседники были полезны и почему\n"
        "- Какие собеседники были бесполезны и почему\n"
        "- Какие хорошие и плохие стороны у беседы\n"
        "- Кто чаще всех писал\n"
        "- Психологический портрет всех участников\n"
        "- Предложение новой темы\n\n"
        "Используй свободный стиль.\n\n"
        + "\n".join(chat_history)
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}"
    }

    body = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(API_URL, json=body, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
