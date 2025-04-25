import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from openrouter import summarize_chat
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text)
async def handle_message(message: Message):
    logging.info(f"Получено сообщение от {message.from_user.id}: {message.text}")
    chat_history = [message.text]
    try:
        summary = await summarize_chat(chat_history)
        await message.reply(summary)
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")
        await message.reply("Произошла ошибка при обработке. Попробуйте позже.")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
    await dp.start_polling(bot)
