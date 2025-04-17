import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.types import Message
from aiogram.filters import CommandStart
from openai import AsyncOpenAI
from os import getenv
from db import save_summary

logging.basicConfig(level=logging.INFO)

# Инициализация
BOT_TOKEN = getenv("BOT_TOKEN")
OPENAI_API_KEY = getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


# Команда /start
@dp.message(CommandStart())
async def handle_start(message: Message):
    await message.answer("👋 Привет! Пришли мне переписку, и я сделаю саммари.")


# Обработка текста
@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip()
    if not text:
        await message.reply("⚠️ Пожалуйста, отправь текст для саммари.")
        return

    await message.reply("✍️ Создаю саммари, подожди немного...")

    try:
        # Генерация саммари через OpenAI
        completion = await openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Сделай краткое саммари следующей переписки:\n\n{text}"
            }],
            temperature=0.7,
            max_tokens=300
        )

        summary = completion.choices[0].message.content.strip()

        await save_summary(message.from_user.id, text, summary)

        await message.reply(f"📌 <b>Саммари:</b>\n{summary}")

    except Exception as e:
        logging.error(f"Ошибка при генерации саммари: {e}")
        await message.reply("❌ Произошла ошибка при создании саммари. Попробуй позже.")
