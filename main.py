import asyncio
from bot import dp, schedule_daily_summary
from aiogram import Bot
from config import TELEGRAM_TOKEN
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    schedule_daily_summary()
    logger.info("🤖 Бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
