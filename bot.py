import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from openrouter import summarize_chat
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise Exception("❌ Не найдены TELEGRAM_TOKEN или OPENROUTER_API_KEY в .env")

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание диспетчера
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text)
async def handle_message(message: Message):
    logger.info(f"Получено сообщение от {message.from_user.id}: {message.text}")
    chat_history = [message.text]

    try:
        summary = await summarize_chat(chat_history, OPENROUTER_API_KEY)
        await message.reply(summary)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await message.reply("⚠️ Произошла ошибка при обработке. Попробуйте позже.")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
    logger.info("🤖 Бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)
