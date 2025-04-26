import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot import router, setup_scheduler
from db import init_db_pool, close_db_pool
from config import TELEGRAM_TOKEN

async def main():
    logging.basicConfig(level=logging.INFO)
    # создаём бота и диспетчер
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # инициализируем пул БД и планировщик
    await init_db_pool()
    setup_scheduler(dp)

    try:
        # запускаем лонг-поллинг
        await dp.start_polling(bot)
    finally:
        # корректно останавливаем scheduler и закрываем ресурсы
        scheduler = dp.get('scheduler')
        if scheduler:
            scheduler.shutdown()
        await close_db_pool()
        # закрываем HTTP-сессию
        session = await bot.get_session()
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
