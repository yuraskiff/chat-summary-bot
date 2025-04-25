import asyncio
from aiogram import Bot, Dispatcher
from bot import dp, bot  # Импортируем уже созданные bot и dp из bot.py

async def main():
    print("🤖 Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
