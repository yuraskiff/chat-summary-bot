
import os
import logging
import openai
import aiosqlite
from datetime import datetime, timedelta
import pytz
import asyncio
import random
import string

from telegram import Update, BotCommand, BotCommandScopeDefault, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ----------------------------------
# 1. Настройка логирования
# ----------------------------------
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------------
# 2. Переменные окружения
# ----------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram")
PORT = int(os.environ.get("PORT", "5000"))
TIMEZONE = os.getenv("TZ", "Europe/Moscow")

openai.api_key = OPENAI_API_KEY

# ----------------------------------
# 3. Настройка базы данных
# ----------------------------------
DB_PATH = "messages.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                user_id TEXT,
                username TEXT,
                text TEXT,
                timestamp DATETIME
            )
        """)
        await db.commit()

async def store_message(chat_id, user_id, username, text):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO chat_messages (chat_id, user_id, username, text, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (chat_id, user_id, username, text, timestamp))
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения: {e}")

async def get_messages_for_today(chat_id):
    since = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, username, text, timestamp
            FROM chat_messages
            WHERE chat_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (chat_id, since))
        return await cursor.fetchall()

async def get_unique_chat_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT chat_id FROM chat_messages")
        rows = await cursor.fetchall()
    return [r[0] for r in rows]

async def cleanup_old_messages(days=7):
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM chat_messages WHERE timestamp < ?", (cutoff,))
        await db.commit()

# ----------------------------------
# 4. Генерация саммари
# ----------------------------------
async def generate_summary(messages):
    if not messages:
        return "Сегодня сообщений не было."

    text_for_prompt = "\n".join(f"[{row[1]}] {row[2]}" for row in messages)[-5000:]
    prompt = (
        "На основе этих сообщений:\n\n"
        + text_for_prompt + "\n\n"
        "Сделай следующее:\n"
        "1. Кратко подведи итоги обсуждений (договорённости, споры, выводы).\n"
        "2. Составь психологические портреты активных участников (по стилю общения).\n"
        "3. Укажи, кто был интересным собеседником, а кто нет, и почему.\n"
        "4. Заверши отчёт шуткой или юмористическим комментарием.\n\n"
    
        "Составь краткое саммари (важные моменты, договорённости, итоги) по сообщениям в чате:\n\n"
        + text_for_prompt
    )

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты ассистент, который составляет саммари сообщений."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"].strip() or "Не удалось получить саммари."
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}")
        return "Произошла ошибка при генерации саммари."

# ----------------------------------
# 5. Планировщик
# ----------------------------------
scheduler = BackgroundScheduler()

def schedule_daily_summary(application, loop):
    tz = pytz.timezone(TIMEZONE)
    trigger = CronTrigger(hour=23, minute=59, timezone=tz)
    scheduler.add_job(
        func=lambda: asyncio.run_coroutine_threadsafe(daily_summary_task(application), loop),
        trigger=trigger,
        id="daily_summary",
        replace_existing=True
    )
    scheduler.add_job(cleanup_old_messages, trigger='cron', hour=3, minute=0, timezone=tz)
    scheduler.start()

async def daily_summary_task(application):
    chat_ids = await get_unique_chat_ids()
    for chat_id in chat_ids:
        messages = await get_messages_for_today(chat_id)
        summary_text = await generate_summary(messages)
        try:
            await application.bot.send_message(chat_id=chat_id, text=f"Ежедневное саммари:\n\n{summary_text}")
        except Exception as e:
            logger.error(f"Ошибка при отправке саммари в чат {chat_id}: {e}")

# ----------------------------------
# 6. Обработчики
# ----------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот, который делает саммари. Добавь меня в группу и дай права админа!")

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    member = await chat.get_member(user.id)

    if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
        await update.message.reply_text("Только админы могут вызывать /summary.")
        return

    chat_id = str(chat.id)
    messages = await get_messages_for_today(chat_id)
    summary_text = await generate_summary(messages)
    await update.message.reply_text(summary_text)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and not update.effective_user.is_bot:
        await store_message(
            str(update.effective_chat.id)
        if random.random() < 0.1:
            jokes = [
                "Хм... любопытненько 🤔",
                "Глубоко... как твой сон по понедельникам 😴",
                "Я бы ответил, но у меня лапки 🐾",
                "GPT-саммари уже в пути. Может. Когда-нибудь. 😅",
                "Это сообщение достойно статуса 'цитата дня' 📜"
            ]
            await update.message.reply_text(random.choice(jokes))
,
            str(update.effective_user.id),
            update.effective_user.username or "NoName",
            update.message.text or ""
        )

# ----------------------------------
# 7. Команды
# ----------------------------------
async def set_commands(application):
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("summary", "Получить саммари за день")
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())

# ----------------------------------
# 8. Запуск
# ----------------------------------
def main():
    loop = asyncio.get_event_loop()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    async def post_init(app):
        await init_db()
        await set_commands(app)

    application.post_init = post_init

    schedule_daily_summary(application, loop)

    full_webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=full_webhook_url,
        url_path=WEBHOOK_PATH
    )

if __name__ == "__main__":
    main()
