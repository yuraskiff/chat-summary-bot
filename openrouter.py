import httpx
import textwrap
from config import OPENROUTER_API_KEY

# Модель DeepSeek-Chat-V3-0324 (free) в OpenRouter
MODEL   = "deepseek/deepseek-chat-v3-0324:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(10.0, read=60.0)

async def summarize_chat(chat_history: list[str], user_prompt: str | None = None) -> str:
    system_msg = "Ты — помощник для анализа чатов."
    default_prompt = textwrap.dedent("""
        Собери сообщения за последние 24 часа и сделай заключение, которое состоит из:
        Какие темы обсуждались
        Какие собеседники были полезны и почему
        Какие собеседники были бесполезны и почему
        Какие хорошие и плохие стороны у беседы
        Кто чаще всех писал
        Психологический портрет участников
        Предложение новой темы
        Короткая шутка на тему беседы
        В саммари используй свободный стиль.
    """).strip()
    prompt   = user_prompt or default_prompt
    chat_text = "\n".join(chat_history)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": f"{prompt}\n\n{chat_text}"}
    ]
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            API_URL,
            json={"model": MODEL, "messages": messages},
            headers=headers
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
