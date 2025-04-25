import asyncio
import logging
from aiogram import Bot
from bot import dp, schedule_daily_summary
from config import TELEGRAM_TOKEN

async def main():
    print("🤖 Бот запускается...")
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode="HTML")
    schedule_daily_summary(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
