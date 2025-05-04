# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Dict, Optional # Убедимся, что Optional импортирован

# Используем Bot для type hinting
from aiogram import Router, Bot
from aiogram.types import Message, InputFile
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Импорты из других модулей проекта
from db.db import (
    get_registered_chats,
    get_messages_for_summary,
    # get_setting, # Убрали, т.к. /set_prompt удален
    # set_setting
)
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID # Импортируем ID админа (int или None)

# --- Настройка шрифта для PDF ---
PDF_FONT = 'Helvetica'
PDF_FONT_PATH = 'DejaVuSans.ttf'
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', PDF_FONT_PATH))
    PDF_FONT = 'DejaVuSans'
    logging.info(f"Шрифт '{PDF_FONT_PATH}' успешно зарегистрирован для PDF.")
except Exception as e:
    logging.warning(
        f"Не найден или не удалось загрузить шрифт '{PDF_FONT_PATH}' ({e}). "
        f"PDF может некорректно отображать кириллицу. Используется '{PDF_FONT}'."
    )
# --- Конец настройки шрифта ---

router = Router()

# --- Проверка ADMIN_CHAT_ID при запуске модуля ---
if ADMIN_CHAT_ID is None:
    logging.warning("ADMIN_CHAT_ID не задан или некорректен в config.py. Админ-команды будут недоступны.")
elif not isinstance(ADMIN_CHAT_ID, int):
     logging.error(f"ADMIN_CHAT_ID из config.py не является числом (тип: {type(ADMIN_CHAT_ID)}). Админ-команды не будут работать.")
     ADMIN_CHAT_ID = None
else:
     logging.info(f"ADMIN_CHAT_ID для проверки прав администратора: {ADMIN_CHAT_ID}")

# --- Хэндлеры админских команд с внутренней проверкой прав ---

# Команда /set_prompt удалена или закомментирована

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """Показывает список активных чатов (проверка админа внутри)."""
    logging.debug(f"Хэндлер /chats вызван пользователем {message.from_user.id}.")
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /chats запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /chats")
    # ... (остальной код cmd_chats) ...
    try:
        logging.info("Запрашиваю список зарегистрированных чатов из БД...")
        chat_ids: List[int] = await get_registered_chats()
        logging.info(f"Получено {len(chat_ids)} ID чатов из БД.")
        if not chat_ids:
            await message.reply("Нет зарегистрированных чатов.")
            logging.info("Список чатов пуст.")
            return
        lines = ["<b>Активные чаты:</b>"]
        logging.info("Начинаю получать информацию о чатах от Telegram API...")
        processed_count = 0
        for cid in chat_ids:
            try:
                logging.debug(f"Получение информации для chat_id: {cid}")
                chat_info = await message.bot.get_chat(chat_id=cid)
                title = chat_info.title or chat_info.full_name or f"ID: {cid}"
                link_part = ""
                if chat_info.type in ('group', 'supergroup', 'channel') and chat_info.invite_link:
                    link_part = f" (<a href='{chat_info.invite_link}'>ссылка</a>)"
                lines.append(f"• {title} (<code>{cid}</code>){link_part}")
                logging.debug(f"Успешно получена информация для chat_id: {cid}")
                processed_count += 1
            except Exception as e:
                logging.warning(f"Не удалось получить информацию о чате {cid}: {e}")
                lines.append(f"• ID: <code>{cid}</code> (ошибка доступа или чат не существует)")
        logging.info(f"Информация о {processed_count} из {len(chat_ids)} чатов собрана.")
        full_text = "\n".join(lines)
        MAX_LEN = 4096
        logging.info(f"Отправляю список чатов пользователю {message.from_user.id}...")
        for i in range(0, len(full_text), MAX_LEN):
            await message.reply(full_text[i:i + MAX_LEN], parse_mode="HTML")
        logging.info("Список чатов успешно отправлен.")
    except Exception as e:
        logging.exception(f"Критическая ошибка при выполнении команды /chats: {e}")
        await message.reply("❌ Произошла ошибка при получении списка чатов.")


@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    """Создает PDF с историей сообщений за 24ч (проверка админа внутри)."""
    logging.debug(f"Хэндлер /pdf вызван пользователем {message.from_user.id}.")
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /pdf запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /pdf")
    # ... (остальной код cmd_pdf) ...
    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip('-').isdigit():
        await message.reply("❗️ Укажите ID чата после команды.\nПример: `/pdf -1001234567890`")
        return
    try: chat_id_to_fetch = int(args[1])
    except ValueError:
        await message.reply("❗️ Некорректный ID чата.")
        return
    try:
        since_time = datetime.now(timezone.utc) - timedelta(days=1)
        logging.info(f"Запрос PDF для чата {chat_id_to_fetch} с {since_time.isoformat()}")
        messages_data: List[Dict] = await get_messages_for_summary(chat_id_to_fetch, since_time)
        if not messages_data:
            await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
            return
        logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter); width, height = letter; margin = 40
        textobject = c.beginText(); textobject.setTextOrigin(margin, height - margin)
        textobject.setFont(PDF_FONT, 8); line_height = 10
        for msg in messages_data:
            msg_timestamp: datetime = msg["timestamp"]
            if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
            elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
            msg_time_str = msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            sender = msg.get("username", "Unknown User"); text = msg.get("text", "") or "[пустое сообщение]"
            header = f"[{msg_time_str}] {sender}:"; lines = simpleSplit(text, PDF_FONT, 8, width - 2 * margin)
            required_lines = 1 + len(lines) + 1
            if textobject.getY() < margin + line_height * required_lines:
                c.drawText(textobject); c.showPage()
                textobject = c.beginText(margin, height - margin); textobject.setFont(PDF_FONT, 8)
            textobject.textLine(header)
            for line in lines: textobject.textLine(f"  {line}")
            textobject.moveCursor(0, line_height / 2)
        c.drawText(textobject); c.save(); buf.seek(0)
        pdf_filename = f"history_{chat_id_to_fetch}_{since_time.strftime('%Y%m%d')}.pdf"
        logging.info(f"Отправка PDF {pdf_filename} пользователю {message.from_user.id}")
        await message.reply_document(InputFile(buf, filename=pdf_filename), caption=f"История чата <code>{chat_id_to_fetch}</code> за последние 24 часа.")
        logging.info("PDF успешно отправлен.")
    except Exception as e:
        logging.exception(f"Ошибка при создании или отправке PDF для чата {chat_id_to_fetch}: {e}")
        await message.reply("❌ Произошла ошибка при создании PDF.")


# --- Функция отправки сводки (с новым промптом) ---
async def send_summary(bot: Bot, chat_id: int):
    """Собирает сообщения за 24 часа, генерирует и отправляет сводку."""
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    now_aware = datetime.now(timezone.utc)
    since_aware = now_aware - timedelta(days=1)

    logging.info(f"Запрос сообщений для сводки чата {chat_id} с {since_aware.isoformat()}")
    try:
        messages_data: List[Dict] = await get_messages_for_summary(chat_id, since=since_aware)
        logging.info(f"📥 Получено сообщений: {len(messages_data)} для чата {chat_id}")
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id}: {e}")
        return

    MIN_MESSAGES_FOR_SUMMARY = 5
    if not messages_data or len(messages_data) < MIN_MESSAGES_FOR_SUMMARY:
        logging.info(f"Недостаточно сообщений ({len(messages_data)}) для сводки в чате {chat_id}.")
        return

    message_blocks: List[str] = []
    for m in messages_data:
        msg_timestamp: datetime = m["timestamp"]
        if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
        ts = msg_timestamp.strftime('%H:%M')
        sender = m.get("username", "Unknown")
        text = m.get("text", "") or "[пусто]"
        MAX_MSG_LEN = 1000
        message_blocks.append(f"[{ts}] {sender}: {text[:MAX_MSG_LEN]}")

    # ----> НОВЫЙ ПРОМПТ ЗДЕСЬ <----
    summary_prompt = """
Проанализируй сообщения из этого чата за последние 24 часа и создай сводку в следующем формате:

1.  **Топ 5 тем:** Перечисли до 5 основных тем, которые обсуждались в чате за этот период. Если тем меньше 5, перечисли все.
2.  **Топ 5 участников:** Перечисли до 5 участников, отправивших наибольшее количество сообщений (укажи только имена/юзернеймы). Если участников меньше 5, перечисли всех.
3.  **Психологический анализ участников:** Для КАЖДОГО участника, упоминаемого в истории сообщений, дай краткий (1-2 предложения) психологический анализ на основе его сообщений (например, стиль общения, предполагаемые черты характера, роль в дискуссии).
4.  **Предложение новой темы:** Предложи ОДНУ новую, интересную тему для обсуждения, которая может быть связана с предыдущими дискуссиями или общими интересами участников (если их можно определить).
5.  **"Токсичный" участник (если есть):** Определи участника, чьи сообщения могли быть наиболее негативными, деструктивными, токсичными или бесполезными для дискуссии, и кратко (1 предложение) объясни почему. Если таких участников нет, напиши "Не выявлено".

Ответ должен быть только на русском языке. Будь объективен и структурирован.
    """.strip()
    logging.info(f"Используется стандартный промпт для чата {chat_id}.")
    # ----> КОНЕЦ НОВОГО ПРОМПТА <----

    logging.info(f"⏳ Отправляем {len(message_blocks)} блоков сообщений в OpenAI для чата {chat_id}...")
    summary_text: Optional[str] = None
    try:
        # Передаем промпт как user_prompt, т.к. summarize_chat ожидает его там
        # (Можно переделать summarize_chat, чтобы он принимал основной промпт как system)
        summary_text = await summarize_chat(message_blocks, user_prompt=summary_prompt)
    except Exception as e:
        logging.exception(f"❌ Ошибка при запросе к OpenAI для чата {chat_id}: {e}")
        try: await bot.send_message(chat_id, "⚠️ Произошла ошибка при генерации сводки.")
        except Exception: pass
        return

    if not summary_text:
        logging.warning(f"OpenAI вернул пустую сводку для чата {chat_id}.")
        return

    try:
        full_summary_text = f"📝 <b>Сводка за последние 24 часа:</b>\n\n{summary_text}"
        MAX_LEN = 4096
        for i in range(0, len(full_summary_text), MAX_LEN):
            await bot.send_message(chat_id, full_summary_text[i:i + MAX_LEN], parse_mode="HTML")
        logging.info(f"✅ Сводка успешно отправлена в чат {chat_id}")
        # Убрали set_setting для времени последней сводки
    except Exception as e:
        logging.exception(f"❌ Ошибка при отправке сводки в чат {chat_id}: {e}")


# --- Настройка планировщика ---
def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик для ежедневной отправки сводок."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    try:
        scheduler.add_job(
            trigger_all_summaries, trigger="cron", hour=21, minute=0,
            args=[bot], id="daily_summaries", replace_existing=True, misfire_grace_time=300
        )
        scheduler.start()
        next_run = scheduler.get_job('daily_summaries').next_run_time
        if next_run: logging.info(f"Планировщик настроен. Следующий запуск сводок: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
        else: logging.warning("Не удалось определить время следующего запуска планировщика.")
    except Exception as e:
        logging.exception(f"❌ Не удалось запустить планировщик: {e}")


# --- Функция запуска сводок по расписанию ---
async def trigger_all_summaries(bot: Bot):
    """Запускает отправку сводок для всех зарегистрированных чатов."""
    logging.info("🚀 Запуск ежедневной рассылки сводок по расписанию...")
    try:
        registered_chats: List[int] = await get_registered_chats()
        logging.info(f"Найдено {len(registered_chats)} зарегистрированных чатов для отправки сводки.")
        if not registered_chats:
            logging.info("Нет зарегистрированных чатов, рассылка не требуется.")
            return

        # Убрана проверка времени последней сводки
        for chat_id in registered_chats:
            logging.info(f"Запуск задачи отправки сводки для чата {chat_id}...")
            try:
                await send_summary(bot, chat_id)
            except Exception as e:
                logging.exception(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")

    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при выполнении trigger_all_summaries: {e}")
    finally:
        logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
