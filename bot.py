import logging
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from openrouter import summarize_chat
from config import TELEGRAM_TOKEN
from db import save_message, get_messages_for_summary
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

@router.message(F.text)
async def handle_message(message: Message):
    logging.info(f"Получено сообщение от {message.from_user.id}: {message.text}")
    await save_message(
        username=message.from_user.username or message.from_user.full_name,
        text=message.text,
        timestamp=datetime.utcnow()
    )

@router.message(F.text == "/start")
async def manual_summary(message: Message):
    await send_summary(message.chat.id)

async def send_summary(chat_id: int):
    since = datetime.utcnow() - timedelta(days=1)
    messages = await get_messages_for_summary(since)
    if not messages:
        await dp.bot.send_message(chat_id, "Нет сообщений за последние 24 часа.")
        return
    try:
        text_blocks = [f"{msg['username']}: {msg['text']}" for msg in messages]
        summary = await summarize_chat(text_blocks)
        await dp.bot.send_message(chat_id, f"📝 Сводка за сутки:\n\n{summary}")

{summary}")
    except Exception as e:
        logging.error(f"Ошибка саммари: {e}")
        await dp.bot.send_message(chat_id, "⚠️ Не удалось создать саммари.")

def schedule_daily_summary():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_summary, 'cron', hour=23, minute=59, args=[os.getenv("CHAT_ID", "")])
    scheduler.start()
