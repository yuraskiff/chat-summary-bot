import os
import logging
import openai
import sqlite3
from datetime import datetime, timedelta
import pytz
import asyncio

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram import BotCommandScopeDefault
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
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен Телеграм-бота
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # API-ключ OpenAI
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL вашего приложения (например, https://<app-name>.onrender.com)
PORT = int(os.environ.get("PORT", "5000"))  # Render передаёт нужный порт через переменную окружения
TIMEZONE = os.getenv("TZ", "Europe/Moscow")  # Часовой пояс

# Задаём API-ключ для openai
openai.api_key = OPENAI_API_KEY

# ----------------------------------
# 3. Инициализация и настройка БД
# ----------------------------------
DB_PATH = "messages.db"

def init_db():
    """Создаёт таблицу для хранения сообщений, если её ещё нет."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                user_id TEXT,
                username TEXT,
                text TEXT,
                timestamp DATETIME
            )
        """)
        conn.commit()

def store_message(chat_id: str, user_id: str, username: str, text: str):
    """Сохраняет сообщение в БД с текущим временем (UTC)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_messages (chat_id, user_id, username, text, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (chat_id, user_id, username, text, datetime.utcnow()))
        conn.commit()

def get_messages_for_today(chat_id: str):
    """Возвращает все сообщения из указанного чата за последние 24 часа."""
    now_utc = datetime.utcnow()
    since_utc = now_utc - timedelta(days=1)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, text, timestamp
            FROM chat_messages
            WHERE chat_id = ? AND timestamp >= ?
        """, (chat_id, since_utc))
        rows = cursor.fetchall()
    return rows

def get_unique_chat_ids():
    """
    Возвращает список уникальных chat_id из таблицы сообщений.
    В реальной ситуации рекомендуется явно хранить список групп.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT chat_id FROM chat_messages")
        rows = cursor.fetchall()
    return [r[0] for r in rows]

# ----------------------------------
# 4. Основная логика создания саммари
# ----------------------------------
async def generate_summary(messages) -> str:
    """
    Запрашивает у OpenAI краткое саммари (выжимку) с использованием Chat API.
    Используется асинхронный вызов (acreate) с моделью GPT‑4.
    Если доступа к GPT‑4 нет, измените model на "gpt-3.5-turbo".
    """
    if not messages:
        return "Сегодня сообщений не было."

    # Используем последние 300 сообщений
    limited_messages = messages[-300:]
    text_for_prompt = "\n".join(
        f"[{row[1]}] {row[2]}" for row in limited_messages
    )
    # Ограничиваем длину текста до 5000 символов
    text_for_prompt = text_for_prompt[-5000:]

    prompt = (
        "Составь краткое саммари (важные моменты, договорённости, итоги) по сообщениям в чате:\n\n"
        + text_for_prompt
    )

    try:
        # Асинхронный вызов к API OpenAI
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",  # если нет доступа к GPT-4, замените на "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "Ты ассистент, который составляет саммари сообщений."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        summary_text = response["choices"][0]["message"]["content"].strip()
        return summary_text if summary_text else "Не удалось получить саммари."
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}")
        return "Произошла ошибка при генерации саммари."

# ----------------------------------
# 5. APScheduler для ежедневной задачи
# ----------------------------------
scheduler = BackgroundScheduler()

def schedule_daily_summary(application):
    """
    Планирует задачу, которая каждый день в 23:59 (по заданному часовому поясу)
    отправляет в каждый чат с сохранёнными сообщениями саммари.
    """
    tz = pytz.timezone(TIMEZONE)
    trigger = CronTrigger(hour=23, minute=59, timezone=tz)
    scheduler.add_job(
        func=lambda: application.create_task(daily_summary_task(application)),
        trigger=trigger,
        id="daily_summary",
        replace_existing=True
    )
    scheduler.start()

async def daily_summary_task(application):
    chat_ids = get_unique_chat_ids()
    for chat_id in chat_ids:
        messages = get_messages_for_today(chat_id)
        summary_text = await generate_summary(messages)
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=f"Ежедневное саммари:\n\n{summary_text}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить саммари в чат {chat_id}: {e}")

# ----------------------------------
# 6. Обработчики бота (handlers)
# ----------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start: отправляет приветственное сообщение."""
    if update.message:
        await update.message.reply_text(
            "Привет! Я бот, который делает саммари. Добавь меня в группу и дай права админа!"
        )

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /summary: отправляет саммари за последние 24 часа."""
    chat_id = str(update.effective_chat.id)
    messages = get_messages_for_today(chat_id)
    summary_text = await generate_summary(messages)
    if update.message:
        await update.message.reply_text(summary_text)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (не команд), сохраняет сообщения в БД."""
    if update.effective_chat is None or update.effective_user is None or update.message is None:
        return
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "NoName"
    text = update.message.text or ""
    store_message(chat_id, user_id, username, text)

# ----------------------------------
# 7. Установка команд для автодополнения в Telegram
# ----------------------------------
async def set_commands(application):
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("summary", "Получить саммари за день")
    ]
    await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())

# ----------------------------------
# 8. Запуск приложения
# ----------------------------------
def main():
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Регистрируем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Устанавливаем команды для автодополнения после инициализации приложения
    async def post_init(app):
        await set_commands(app)
    application.post_init = post_init

    # Планируем ежедневное саммари
    schedule_daily_summary(application)

    # Определяем путь вебхука
    webhook_path = "/telegram"
    full_webhook_url = f"{WEBHOOK_URL}{webhook_path}"

    # Запускаем приложение через вебхук (Render передает нужный PORT через переменную окружения)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=full_webhook_url,
        url_path=webhook_path
    )

if __name__ == "__main__":
    main()
