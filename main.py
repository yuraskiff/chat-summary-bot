import asyncio
import logging

from aiogram import Bot, Dispatcher

# Импортируем все три роутера
from bot.handlers.user_handlers import router as user_router
from bot.handlers.chat_handlers import router as chat_router
from bot.handlers.admin_handlers import router as admin_router, setup_scheduler
from bot.middleware.auth_middleware import AuthMiddleware

from config.config import BOT_TOKEN
from db.db import init_pool, close_pool

async def main():
    # Логи
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

    # Бот и диспетчер
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    dp  = Dispatcher()

    # Инициализация БД
    await init_pool()

    # Регистрируем middleware (сейчас он лишь блокирует админ-команды от чужих)
    dp.message.middleware(AuthMiddleware())

    # Подключаем роутеры
    dp.include_router(user_router)
    dp.include_router(chat_router)
    dp.include_router(admin_router)

    # Планировщик автосводок
    setup_scheduler(dp)

    # Сбрасываем webhook и пропускаем все старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted and pending updates dropped.")

    try:
        logging.info("Bot is starting polling...")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        # Завершаем всё аккуратно
        sched = dp.get("scheduler")
        if sched:
            sched.shutdown()

        await close_pool()
        session = await bot.get_session()
        await session.close()
        logging.info("Bot stopped successfully.")

if __name__ == "__main__":
    asyncio.run(main())
