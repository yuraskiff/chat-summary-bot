import os
import logging
import openai
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL вашего приложения на Render (например, https://<app-name>.onrender.com)
PORT = int(os.environ.get("PORT", "5000"))  # Порт, который отдаёт Render
TIMEZONE = os.getenv("TZ", "Europe/Moscow")  # Часовой пояс

# Задаём API ключ для openai
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
            WHERE chat_id = ?
              AND timestamp >= ?
        """, (chat_id, since_utc))
        rows = cursor.fetchall()
    return rows

def get_unique_chat_ids():
    """
    Возвращает список уникальных chat_id из таблицы (упрощённый пример).
    В реальной ситуации рекомендуется хранить список групп явно.
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
    Запрашивает у OpenAI краткую выжимку (саммари) с использованием Chat API.
    Использует модель GPT‑4. Ограничивает объём передаваемых сообщений,
    чтобы не превысить лимиты.
    """
    if not messages:
        return "Сегодня сообщений не было."

    # Ограничиваем до последних 300 сообщений
    limited_messages = messages[-300:]
    text_for_prompt = "\n".join(
        f"[{row[1]}] {row[2]}"  # формат: username: сообщение
        for row in limited_messages
    )
    # Ограничиваем длину текста до 5000 символов
    text_for_prompt = text_for_prompt[-5000:]

    prompt = (
        "Составь краткое саммари (важные моменты, договорённости, итоги) "
        "по сообщениям в чате:\n\n" + text_for_prompt
    )

    try:
        # Асинхронный вызов OpenAI Chat API
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
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
    генерирует саммари для каждого чата.
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
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я бот, который делает саммари. Добавь меня в группу и дай права админа!"
    )

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /summary — ручной вызов саммари за последние 24 часа."""
    chat_id = str(update.effective_chat.id)
    messages = get_messages_for_today(chat_id)
    summary_text = await generate_summary(messages)
    await update.message.reply_text(summary_text)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (не команд), сохраняет их в БД."""
    # Проверяем, что необходимые данные присутствуют
    if update.effective_chat is None or update.effective_user is None or update.message is None:
        return

    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "NoName"
    text = update.message.text or ""

    store_message(chat_id, user_id, username, text)

# ----------------------------------
# 7. Запуск приложения
# ----------------------------------

def main():
    # Инициализация базы данных
    init_db()

    # Создаем приложение Telegram бота
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Регистрируем команды и обработчики сообщений
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Планируем ежедневное саммари
    schedule_daily_summary(application)

    # Настройка вебхука (например, для Render)
    webhook_path = "/telegram"
    full_webhook_url = f"{WEBHOOK_URL}{webhook_path}"

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=full_webhook_url,
        url_path=webhook_path
    )

if __name__ == "__main__":
    main()
