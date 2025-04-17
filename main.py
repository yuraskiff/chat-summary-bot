import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from gpt import generate_summary
from db import init_db, add_group, get_all_groups
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

async def collect_and_summarize(chat_id: int):
    print(f"📚 Собираю сообщения из группы {chat_id}...")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=1)
    history = []

    async for message in bot.get_chat_history(chat_id=chat_id, limit=1000):
        if message.date < start_time:
            break
        if message.text:
            sender = message.from_user.full_name if message.from_user else "Неизвестно"
            history.append(f"{sender}: {message.text}")

    if not history:
        await bot.send_message(chat_id, "😕 За последние сутки сообщений не найдено.")
        return

    formatted = "\n".join(history)
    summary = generate_summary(formatted)
    await bot.send_message(chat_id, f"📝 Ежедневный отчёт:\n\n{summary}")

@dp.message(F.text == "/summary")
async def summary_command(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Я работаю только в группах!")
        return
    await message.answer("⏳ Формирую саммари, подожди немного...")
    await collect_and_summarize(chat_id=message.chat.id)
    await add_group(message.chat.id)

async def main():
    await init_db()
    scheduler = AsyncIOScheduler()
    groups = await get_all_groups()
    for group_id in groups:
        scheduler.add_job(collect_and_summarize, 'cron', hour=0, minute=0, args=[group_id])
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


@dp.message(F.text == "/health")
async def health_check(message: types.Message):
    from db import async_session
    try:
        async with async_session() as session:
            await session.execute("SELECT 1")
        await message.answer("✅ Я жив! Telegram и БД на связи.")
    except Exception as e:
        await message.answer(f"⚠️ Проблема с БД: {e}")

from time import perf_counter
from db import count_groups

async def log_error(bot: Bot, text: str):
    log_chat = os.getenv("LOG_CHAT_ID")
    if log_chat:
        try:
            await bot.send_message(int(log_chat), f"❌ Ошибка:\n{text}")
        except Exception as e:
            print("Ошибка при отправке в лог-чат:", e)

@dp.message(F.text == "/ping")
async def ping_command(message: types.Message):
    start = perf_counter()
    elapsed = (perf_counter() - start) * 1000
    await message.answer(f"🏓 Pong! ⏱ {int(elapsed)} ms")

@dp.message(F.text == "/stats")
async def stats_command(message: types.Message):
    try:
        group_count = await count_groups()
        await message.answer(f"📊 Статистика:\n- Групп в базе: {group_count}")
    except Exception as e:
        await message.answer("⚠️ Ошибка при получении статистики")
        await log_error(bot, str(e))
