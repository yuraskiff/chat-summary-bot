
import os
import logging
import datetime
import openai
import sqlite3
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("7396613294:AAF0IoZM2rXOQz0bUQ6RSSx3aR7NwPSjgQQ")
OPENAI_API_KEY = os.getenv("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")
openai.api_key = OPENAI_API_KEY

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("messages.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS messages (
                date TEXT,
                username TEXT,
                text TEXT
            )""")
conn.commit()

# --- ОБРАБОТКА СООБЩЕНИЙ ---
async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == CHAT_ID and update.message and update.message.text:
        username = update.message.from_user.username or update.message.from_user.first_name
        text = update.message.text
        date = str(datetime.date.today())
        c.execute("INSERT INTO messages (date, username, text) VALUES (?, ?, ?)", (date, username, text))
        conn.commit()

# --- ГЕНЕРАЦИЯ САММАРИ ---
def generate_summary(messages):
    joined = "\n".join(messages)
    prompt = (
        "Ты бот-хроникёр, который анализирует переписку группы и пишет краткий отчёт."
        " Вот переписка за день:\n"
        f"{joined}\n"
        "Сделай краткое саммари: темы, активные и неактивные участники, сложные вопросы, плюсы и минусы людей, психологические портреты."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return response["choices"][0]["message"]["content"]

# --- ОТПРАВКА САММАРИ ---
async def send_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    today = str(datetime.date.today())
    c.execute("SELECT username, text FROM messages WHERE date = ?", (today,))
    rows = c.fetchall()
    if rows:
        messages = [f"{username}: {text}" for username, text in rows]
        summary = generate_summary(messages)
        await context.bot.send_message(chat_id=CHAT_ID, text=summary)

# --- КОМАНДЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я собираю сообщения и каждый вечер делаю саммари дня ✨")

async def manual_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = str(datetime.date.today())
    c.execute("SELECT username, text FROM messages WHERE date = ?", (today,))
    rows = c.fetchall()
    if rows:
        messages = [f"{username}: {text}" for username, text in rows]
        summary = generate_summary(messages)
        await update.message.reply_text(summary)
    else:
        await update.message.reply_text("Сегодня ещё нет сообщений.")

# --- ЗАПУСК ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("summary", manual_summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(send_daily_summary(ContextTypes.DEFAULT_TYPE())), 'cron', hour=23, minute=59)
    scheduler.start()

    logger.info("Бот запущен")
    app.run_polling()
