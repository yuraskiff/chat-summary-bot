import asyncio
from bot import dp, bot
from db import init_db

async def main():
    print("🚀 Starting bot...")

    # Инициализация базы данных
    await init_db()

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("❌ Bot stopped!")
