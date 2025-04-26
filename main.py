import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.fsm.storage.memory import MemoryStorage
from bot import router, setup_scheduler
from db import init_db_pool, close_db_pool
from config import TELEGRAM_TOKEN

async def on_startup(dp: Dispatcher):
    logging.info("🚀 Запуск бота...")
    await init_db_pool()
    setup_scheduler(dp)

async def on_shutdown(dp: Dispatcher):
    logging.info("🔌 Остановка бота...")
    sched = dp.get('scheduler')
    if sched:
        sched.shutdown()
    await close_db_pool()

def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TELEGRAM_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)

if __name__ == "__main__":
    main()
