import io
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from db.db import (
    get_chat_ids_for_summary,
    get_messages_for_summary,
    get_setting,
    set_setting
)
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID

router = Router()

@router.message(Command("summary"))
async def cmd_summary(message: Message):
    """
    /summary — моментальная сводка по текущему чату.
    Работает у всех пользователей.
    """
    await send_summary(message.bot, message.chat.id)

@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    """
    /set_prompt <текст> — меняет шаблон сводки.
    Только вы (по своему user_id) можете вызывать эту команду.
    """
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    new_prompt = message.get_args().strip()
    if not new_prompt:
        return await message.reply("❗️ Укажите новый шаблон после команды.")
    await set_setting("summary_prompt", new_prompt)
    await message.reply("✅ Шаблон сводки обновлён.")

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """
    /chats — список chat_id, где есть сохранённые сообщения.
    Команда только для вас.
    """
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    ids = [cid for cid in await get_chat_ids_for_summary(None) if cid is not None]
    if not ids:
        return await message.reply("Нет активных чатов.")

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
    """
    /pdf <chat_id> — PDF-отчёт за последние 24 часа.
    Только вы.
    """
    if message.from_user.id != ADMIN_CHAT_ID:
        return

    parts = message.get_args().split()
    if not parts or not parts[0].isdigit():
        return await message.reply("❗️ Укажите chat_id: `/pdf 123456789`")

    cid = int(parts[0])
    since = datetime.utcnow() - timedelta(days=1)
    msgs = await get_messages_for_summary(cid, since)
    if not msgs:
        return await message.reply("Нет сообщений за последние 24 часа.")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    text_obj = c.beginText(40, 750)
    text_obj.setFont("Helvetica", 10)

    for m in msgs:
        ts = m["timestamp"].strftime("%Y-%m-%d %H:%M")
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
    """
    Вспомогательная функция: делает сводку за 24 часа и отправляет её.
    """
    since = datetime.utcnow() - timedelta(days=1)
    msgs = await get_messages_for_summary(chat_id, since)
    if not msgs:
        return await bot.send_message(chat_id, "Нет сообщений за последние 24 часа.")
    blocks = [f"{m['username']}: {m['text']}" for m in msgs]
    prompt = await get_setting("summary_prompt")
    summary = await summarize_chat(blocks, prompt)
    if not summary:
        return await bot.send_message(chat_id, "Не удалось получить сводку.")
    await bot.send_message(chat_id, f"📝 Сводка за сутки:\n\n{summary}")

def setup_scheduler(dp):
    """
    Инициализация планировщика для ежедневных рассылок.
    """
    scheduler = AsyncIOScheduler(timezone="Europe/Tallinn")
    scheduler.add_job(
        lambda: dp.loop.create_task(send_all_summaries(dp.bot)),
        trigger="cron", hour=23, minute=59
    )
    scheduler.start()
    dp['scheduler'] = scheduler

async def send_all_summaries(bot: Bot):
    since = datetime.utcnow() - timedelta(days=1)
    for cid in await get_chat_ids_for_summary(since):
        await send_summary(bot, cid)
