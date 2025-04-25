import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def summarize_chat(messages):
    prompt = "\n".join(messages) + "\n\nСделай веселое и интересное саммари этого чата:"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourdomain.com",
        "X-Title": "Chat Summary Bot"
    }
    body = {
        "model": "openchat/openchat-3.5",
        "messages": [
            {"role": "system", "content": "Ты бот, который создает юмористическое саммари беседы."},
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", json=body, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            return f"OpenRouter error: {exc}"
