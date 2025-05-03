import asyncio
import logging

from aiogram import Bot, Dispatcher
from config.config import BOT_TOKEN
from db.db import init_pool, close_pool
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Инициализация бота и диспетчера
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    # Инициализация подключения к базе данных
    await init_pool()

    # Регистрируем хендлеры и middleware
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.message.middleware(AuthMiddleware())

    # Запускаем планировщик автосводок
    setup_scheduler(dp)

    # Удаляем возможный Webhook и сбрасываем все накопленные апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted and pending updates dropped.")

    try:
        logging.info("Bot is starting polling...")
        # Запускаем polling и пропускаем все старые апдейты
        await dp.start_polling(bot, skip_updates=True)
    finally:
        # Останавливаем планировщик
        sched = dp.get('scheduler')
        if sched:
            sched.shutdown()

        # Закрываем пул базы данных
        await close_pool()

        # Закрываем HTTP-сессию бота
        session = await bot.get_session()
        await session.close()
        logging.info("Bot stopped successfully.")

if __name__ == "__main__":
    asyncio.run(main())
