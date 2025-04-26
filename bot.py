import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from openrouter import summarize_chat
from db import save_message, get_chat_ids_for_summary, get_messages_for_summary
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone, timedelta

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def handle_message(message: Message):
    logging.info(f"Получено сообщение от {message.chat.id}/{message.from_user.id}: {message.text}")
    await save_message(
        chat_id=message.chat.id,
        username=message.from_user.username or message.from_user.full_name,
        text=message.text,
        timestamp=datetime.now(timezone.utc)
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет! Я буду собирать сообщения за сутки и присылать сводку. Просто добавь меня в любой чат — и я начну работу.")

@router.message(Command("summary"))
async def cmd_manual_summary(message: Message):
    await send_summary(message.bot, message.chat.id)

async def send_summary(bot: Bot, chat_id: int):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    msgs = await get_messages_for_summary(chat_id, since)
    if not msgs:
        await bot.send_message(chat_id, "Нет сообщений за последние 24 часа.")
        return

    try:
        blocks = [f"{m['username']}: {m['text']}" for m in msgs]
        summary = await summarize_chat(blocks)
        await bot.send_message(chat_id, f"📝 Сводка за сутки:\n\n{summary}")
    except Exception:
        logging.exception("Ошибка генерации сводки")
        await bot.send_message(chat_id, "⚠️ Не удалось сгенерировать сводку.")

async def send_summaries_all(bot: Bot):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    chat_ids = await get_chat_ids_for_summary(since)
    for cid in chat_ids:
        await send_summary(bot, cid)

def setup_scheduler(dispatcher: Dispatcher):
    scheduler = AsyncIOScheduler(timezone="Europe/Tallinn")
    scheduler.add_job(
        lambda: dispatcher.loop.create_task(send_summaries_all(dispatcher.bot)),
        'cron', hour=23, minute=59
    )
    scheduler.start()
    dispatcher['scheduler'] = scheduler
