import asyncio
import logging

from aiogram import Bot, Dispatcher
from config.config import BOT_TOKEN
from db.db import init_pool, close_pool
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    await init_pool()

    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.message.middleware(AuthMiddleware())

    setup_scheduler(dp)

    try:
        logging.info("Bot is starting...")
        await dp.start_polling(bot)
    finally:
        sched = dp.get('scheduler')
        if sched:
            sched.shutdown()
        await close_pool()
        session = await bot.get_session()
        await session.close()
        logging.info("Bot stopped successfully.")

if __name__ == "__main__":
    asyncio.run(main())
