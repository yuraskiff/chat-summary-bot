import io
from datetime import datetime, timedelta, timezone

from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from db.db import (
    get_registered_chats,
    get_messages_for_summary,
    get_setting,
    set_setting
)
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID

router = Router()

@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    """Меняет шаблон сводки — только для администратора."""
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    new_prompt = message.get_args().strip()
    if not new_prompt:
        await message.reply("❗️ Укажите новый шаблон после команды.")
        return

    await set_setting("summary_prompt", new_prompt)
    await message.reply("✅ Шаблон сводки обновлён.")

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """Показывает все зарегистрированные чаты — только для администратора."""
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    ids = await get_registered_chats()
    if not ids:
        await message.reply("Нет активных чатов.")
        return

    lines = []
    for cid in ids:
        try:
            info = await message.bot.get_chat(cid)
            title = info.title or info.full_name or str(cid)
        except:
            title = str(cid)
        lines.append(f"{cid} — {title}")

    await message.reply("Активные чаты:\n" + "\n".join(lines))

@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    """Генерирует PDF-отчёт за последние 24 часа — только для администратора."""
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    parts = message.get_args().split()
    if not parts or not parts[0].isdigit():
        await message.reply("❗️ Укажите chat_id: `/pdf 123456789`")
        return

    cid = int(parts[0])
    since = datetime.now(timezone.utc) - timedelta(days=1)
    msgs = await get_messages_for_summary(cid, since)
    if not msgs:
        await message.reply("Нет сообщений за последние 24 часа.")
        return

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    text = c.beginText(40, 750)
    text.setFont("Helvetica", 10)

    for m in msgs:
        ts = m["timestamp"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        line = f"{ts} | {m['username']}: {m['text']}"
        text.textLine(line[:1000])
        if text.getY() < 40:
            c.drawText(text)
            c.showPage()
            text = c.beginText(40, 750)
            text.setFont("Helvetica", 10)

    c.drawText(text)
    c.save()
    buf.seek(0)
    await message.reply_document(buf, filename=f"history_{cid}.pdf")


async def send_summary(bot: Bot, chat_id: int):
    """Вспомогательная: собирает за сутки, спрашивает модель, шлёт сводку."""
    since = datetime.now(timezone.utc) - timedelta(days=1)
    msgs = await get_messages_for_summary(chat_id, since)
    if not msgs:
        await bot.send_message(chat_id, "Нет сообщений за последние 24 часа.")
        return

    blocks = [f"{m['username']}: {m['text']}" for m in msgs]
    prompt = await get_setting("summary_prompt")
    summary = await summarize_chat(blocks, prompt)
    if not summary:
        await bot.send_message(chat_id, "Не удалось получить сводку.")
        return

    await bot.send_message(chat_id, f"📝 Сводка за сутки:\n\n{summary}")


def setup_scheduler(dp):
    """Планировщик автосводок на 23:59 Europe/Tallinn."""
    scheduler = AsyncIOScheduler(timezone="Europe/Tallinn")
    scheduler.add_job(
        lambda: dp.loop.create_task(send_all_summaries(dp.bot)),
        trigger="cron",
        hour=23,
        minute=59
    )
    scheduler.start()
    dp['scheduler'] = scheduler


async def send_all_summaries(bot: Bot):
    """Ежедневная рассылка всем зарегистрированным чатам."""
    since = datetime.now(timezone.utc) - timedelta(days=1)
    for cid in await get_registered_chats():
        await send_summary(bot, cid)
