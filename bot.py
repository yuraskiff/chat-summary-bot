import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from gpt import get_summary

import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if not text:
        await message.reply("❗️Пожалуйста, отправь текст для саммари.")
        return

    await message.reply("✍️ Пишу саммари...")
    summary = await get_summary(text)
    await message.reply(f"📌 <b>Саммари:</b>
{summary}")
