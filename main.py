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
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    # Уменьшаем подробность логов aiohttp/aiogram
    logging.getLogger("aiogram.client.session").setLevel(logging.ERROR)

    # Создаём экземпляр бота и диспетчера
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    dp  = Dispatcher()

    # Инициализация пула БД с логированием
    try:
        await init_pool()
        logging.info("✅ Пул БД успешно инициализирован")
    except Exception as e:
        logging.error("❌ Не удалось инициализировать БД: %s", e)
        return  # без БД бот дальше не стартует

    # Регистрируем middleware (блокировка админ-команд для чужих пользователей)
    dp.message.middleware(AuthMiddleware())

    # Подключаем все роутеры
    dp.include_router(user_router)
    dp.include_router(chat_router)
    dp.include_router(admin_router)

    # Настраиваем планировщик автосводок
    setup_scheduler(dp)

    # Сбрасываем вебхук и убираем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook удалён, старые обновления сброшены.")

    try:
        logging.info("🚀 Бот запускается в режиме polling...")
        await dp.start_polling(bot, skip_updates=True)
    finally:
        # При остановке корректно выключаем планировщик, пул и сессию бота
        sched = dp.get("scheduler")
        if sched:
            sched.shutdown()

        await close_pool()

        # В aiogram 3.x правильнее закрывать session так:
        try:
            await bot.session.close()
        except AttributeError:
            # Для старых версий aiogram:
            session = await bot.get_session()
            await session.close()

        logging.info("🛑 Бот остановлен успешно.")

if __name__ == "__main__":
    asyncio.run(main())
