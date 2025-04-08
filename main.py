
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
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- БАЗА ДАННЫХ ---
import os
if os.path.exists("messages.db"):
    os.remove("messages.db")
conn = sqlite3.connect("messages.db", check_same_thread=False)
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS messages")
c.execute("""CREATE TABLE IF NOT EXISTS messages (
                date TEXT,
                username TEXT,
                text TEXT
            )""")
conn.commit()

# --- ОБРАБОТКА СООБЩЕНИЙ ---
async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    logger.info(f"Новое сообщение в чате {chat.id} от @{user.username or user.first_name}")

    try:
        member = await context.bot.get_chat_member(chat.id, context.bot.id)
        is_admin = member.status in ['administrator', 'creator']
    except Exception as e:
        logger.warning(f"Ошибка при проверке прав администратора: {e}")
        return

    if update.message and update.message.text:
        username = user.username or user.first_name
        text = update.message.text
        date = str(datetime.date.today())
        c.execute("INSERT INTO messages (date, chat_id, username, text) VALUES (?, ?, ?, ?)", (date, chat.id, username, text))
        conn.commit()
        logger.info(f"Сохранено сообщение: {username}: {text}")


    if not is_admin:
        logger.info(f"Бот не является админом в чате {chat.id}, сообщение проигнорировано.")
        return
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
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("debug", debug))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("topics", topics))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(send_daily_summary(ContextTypes.DEFAULT_TYPE())), 'cron', hour=23, minute=59)
    scheduler.start()

    logger.info("Бот запущен")
    app.run_polling()

# --- ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ---

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Я на связи!")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    debug_info = (
        f"👤 Пользователь: {user.first_name} (@{user.username})\n"
        f"🆔 User ID: {user.id}\n"
        f"💬 Chat ID: {chat.id}\n"
        f"👥 Chat Type: {chat.type}"
    )
    await update.message.reply_text(debug_info)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /profile @username")
        return
    username = context.args[0].lstrip('@')
    today = str(datetime.date.today())
    c.execute("SELECT text FROM messages WHERE username = ? AND date = ?", (username, today))
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("Нет сообщений от этого пользователя сегодня.")
        return
    messages = [r[0] for r in rows]
    prompt = (
        f"Проанализируй следующие сообщения пользователя @{username} и составь краткий психологический портрет:\n"
        + "\n".join(messages)
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    await update.message.reply_text(response["choices"][0]["message"]["content"])

async def topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = str(datetime.date.today())
    c.execute("SELECT text FROM messages WHERE date = ?", (today,))
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("Сегодня ещё нет обсуждений.")
        return
    joined = "\n".join([r[0] for r in rows])
    prompt = (
        "Выдели основные темы, которые поднимались в этой переписке:\n" + joined
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    await update.message.reply_text("🧵 Темы дня:\n" + response["choices"][0]["message"]["content"])
