from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import CommandStart
from config import TELEGRAM_TOKEN, OPENAI_API_KEY
from openai import AsyncOpenAI
from db import save_summary

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Привет! Пришли мне текст, и я сделаю для него саммари 🧠")

@dp.message(F.text)
async def handle_message(message: Message):
    user_text = message.text

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты помощник, который делает краткое саммари текста."},
            {"role": "user", "content": user_text}
        ]
    )

    summary = response.choices[0].message.content.strip()
    await message.reply(f"📌 <b>Саммари:</b>
{summary}")
    await save_summary(user_text, summary)