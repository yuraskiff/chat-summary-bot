from aiogram import Router, F
from aiogram.types import Message
from aiolimiter import AsyncLimiter
from openrouter import get_summary_from_openrouter

router = Router()

# 🛡️ Telegram flood control limiter
limiter = AsyncLimiter(max_rate=1, time_period=2)

@router.message(F.text)
async def handle_message(message: Message):
    try:
        # 💬 Формируем запрос к LLM
        messages = [
            {
                "role": "system",
                "content": "Ты веселый AI, который создает короткие и забавные саммари сообщений чата. Будь креативным, иногда шути, используй эмодзи!"
            },
            {
                "role": "user",
                "content": message.text
            }
        ]

        summary = await get_summary_from_openrouter(messages)

        async with limiter:
            await message.reply(summary)

    except Exception as e:
        print("⚠️ Ошибка при обработке сообщения:", e)
        await message.reply("Что-то пошло не так 🤖💥")
