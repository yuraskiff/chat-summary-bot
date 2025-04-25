import asyncio
from bot import dp, schedule_daily_summary

async def main():
    print("🤖 Бот запускается...")
    schedule_daily_summary()  # Запускаем планировщик внутри event loop
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
