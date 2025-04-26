import logging
import io
from datetime import datetime, timezone, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from db import (
    save_message, get_messages_for_summary,
    get_chat_ids_for_summary, get_setting, set_setting
)
from openrouter import summarize_chat

router = Router()

@router.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def handle_message(message: Message):
    await save_message(
        chat_id=message.chat.id,
        username=message.from_user.username or message.from_user.full_name,
        text=message.text,
        timestamp=datetime.now(timezone.utc)
    )

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "Привет! Я собираю сообщения и раз в день делаю сводки.\n"
        "Используй /summary для мгновенного отчёта."
    )

@router.message(Command("summary"))
async def cmd_summary(message: Message):
    await send_summary(message.bot, message.chat.id)

@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    text = message.get_args().strip()
    if not text:
        return await message.reply("❗️ Укажите новый шаблон после команды.")
    await set_setting("summary_prompt", text)
    await message.reply("✅ Шаблон сводки обновлён.")

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    ids = await get_chat_ids_for_summary(None)
    lines = []
    for cid in ids:
        try:
            info = await message.bot.get_chat(cid)
            title = info.title or info.full_name
        except:
            title = str(cid)
        lines.append(f"{cid} — {title}")
    text = "\n".join(lines) if lines else "Нет активных чатов."
    await message.reply(f"Активные чаты:\n{text}")

@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    if message.chat.id != ADMIN_CHAT_ID:
        return
    args = message.get_args().strip().split()
    if not args or not args[0].isdigit():
        return await message.reply("❗️ Укажите chat_id: `/pdf 123456789`")
    cid = int(args[0])
    since = datetime.now(timezone.utc) - timedelta(days=1)
    msgs = await get_messages_for_summary(cid, since)
    if not msgs:
        return await message.reply("Нет сообщений за последние 24 часа.")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    text_obj = c.beginText(40, 750)
    text_obj.setFont("Helvetica", 10)
    for m in msgs:
        ts = m["timestamp"].astimezone().strftime("%Y-%m-%d %H:%M")
        line = f"{ts} | {m['username']}: {m['text']}"
        text_obj.textLine(line[:1000])
        if text_obj.getY() < 40:
            c.drawText(text_obj)
            c.showPage()
            text_obj = c.beginText(40, 750)
            text_obj.setFont("Helvetica", 10)
    c.drawText(text_obj)
    c.save()
    buf.seek(0)
    await message.reply_document(buf, filename=f"history_{cid}.pdf")

async def send_summary(bot: Bot, chat_id: int):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    msgs = await get_messages_for_summary(chat_id, since)
    if not msgs:
        return await bot.send_message(chat_id, "Нет сообщений за последние 24 часа.")
    blocks = [f"{m['username']}: {m['text']}" for m in msgs]
    prompt = await get_setting("summary_prompt")
    summary = await summarize_chat(blocks, prompt)
    await bot.send_message(chat_id, f"📝 Сводка за сутки:\n\n{summary}")

def setup_scheduler(dp: Dispatcher):
    scheduler = AsyncIOScheduler(timezone="Europe/Tallinn")
    scheduler.add_job(
        lambda: dp.loop.create_task(send_all_summaries(dp.bot)),
        'cron', hour=23, minute=59
    )
    scheduler.start()
    dp['scheduler'] = scheduler

async def send_all_summaries(bot: Bot):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    for cid in await get_chat_ids_for_summary(since):
        await send_summary(bot, cid)
