import asyncio
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.config import BOT_TOKEN, ADMIN_CHAT_ID, DEFAULT_SUMMARY_TYPE
from db.db import init_pool, close_pool, fetch
from bot.middleware.auth_middleware import AuthMiddleware
from bot.handlers.user_handlers import router as user_router
from bot.handlers.admin_handlers import router as admin_router
from api_clients.openrouter import generate_summary

# Инициализация бота и диспетчера глобально
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.message.middleware(AuthMiddleware())
dp.include_router(user_router)
dp.include_router(admin_router)

async def daily_job():
    # Суммируем каждый чат за последние 24 часа
    chats = await fetch("SELECT chat_id FROM chats;")
    for row in chats:
        chat_id = row["chat_id"]
        msgs = await fetch(
            "SELECT content FROM messages WHERE chat_id=$1 "
            "AND created_at > now() - interval '24 hours' "
            "ORDER BY created_at;",
            chat_id
        )
        texts = [r["content"] for r in msgs]
        # Получаем тип из настроек
        st = await fetch("SELECT value FROM settings WHERE key='summary_type';")
        summary_type = st[0]["value"] if st else DEFAULT_SUMMARY_TYPE
        summary = await generate_summary(texts, summary_type)
        if summary:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"Сводка по чату {chat_id}:\n\n{summary}"
            )

async def main():
    # Инициализация подключения к БД
    await init_pool()

    # Удаляем любые установленные вебхуки и очищаем очередь getUpdates
    await bot.delete_webhook(drop_pending_updates=True)

    # Настройка планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_job, "cron", hour=0, minute=0)
    scheduler.start()

    try:
        # Запуск polling
        await dp.start_polling(bot)
    finally:
        # Завершение
        scheduler.shutdown()
        await close_pool()
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
