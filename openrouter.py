import httpx
import textwrap
from config import OPENROUTER_API_KEY

MODEL   = "meta-llama/llama-3.1-8b-instruct:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

async def summarize_chat(chat_history: list[str]) -> str:
    system_msg = "Ты — помощник для анализа чатов."
    user_prompt = textwrap.dedent("""
        Собери сообщения за последние 24 часа и сделай заключение, которое состоит из следующей информации:

        - Какие темы обсуждались
        - Какие собеседники были полезны и почему
        - Какие собеседники были бесполезны и почему
        - Какие хорошие и плохие стороны у беседы
        - Кто чаще всех писал
        - Психологический портрет всех участников
        - Предложение новой темы

        Используй свободный стиль.
    """).strip()

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": f"{user_prompt}\n\n{'\n'.join(chat_history)}"}
    ]
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(API_URL, json={"model": MODEL, "messages": messages}, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
