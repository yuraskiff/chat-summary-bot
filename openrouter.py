import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-3-8b-instruct"  # Убедись что это именно твоя выбранная модель!

async def summarize_chat(chat_history):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://your-app-name.onrender.com",  # Можешь указать свой домен или оставить так
        "X-Title": "SummaryBot"
    }

    messages = [
        {
            "role": "user",
            "content": (
                "Собери сообщения за последние 24 часа и сделай заключение, которое состоит из следующей информации:\n\n"
                "- Какие темы обсуждались\n"
                "- Какие собеседники были полезны и почему\n"
                "- Какие собеседники были бесполезны и почему\n"
                "- Какие хорошие и плохие стороны у беседы\n"
                "- Кто чаще всех писал\n"
                "- Психологический портрет всех участников\n"
                "- Предложение новой темы\n\n"
                "Используй свободный, живой стиль изложения.\n\n"
                "Сообщения чата:\n\n" + "\n".join(chat_history)
            )
        }
    ]

    data = {
        "model": OPENROUTER_MODEL,
        "messages": messages
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(OPENROUTER_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
