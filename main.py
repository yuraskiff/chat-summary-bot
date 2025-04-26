
import asyncio
import logging
from aiogram import Bot, Dispatcher
from config.config import BOT_TOKEN
from db.db import init_pool, close_pool
from bot.handlers.user_handlers import router as user_router
from bot.middleware.auth_middleware import AuthMiddleware

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    
    await init_pool()
    
    dp.include_router(user_router)
    dp.message.middleware(AuthMiddleware())

    try:
        logging.info("Starting bot...")
        await dp.start_polling(bot)
    finally:
        await close_pool()
        logging.info("Bot stopped successfully.")

if __name__ == "__main__":
    asyncio.run(main())
