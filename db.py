import asyncio
from bot import dp, schedule_daily_summary

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    from aiogram import Bot
    from config import TELEGRAM_TOKEN

    bot = Bot(token=TELEGRAM_TOKEN, parse_mode="HTML")
    schedule_daily_summary()
    asyncio.run(dp.start_polling(bot))
