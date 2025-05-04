# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

# Используем F для Magic Filter и Bot для type hinting
from aiogram import Router, Bot, F
from aiogram.types import Message, InputFile
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from db.db import (
    get_registered_chats,
    get_messages_for_summary,
    get_setting,
    set_setting
)
# Убедитесь, что импорт функции из openrouter корректен
from api_clients.openrouter import summarize_chat
# ----> ИМПОРТИРУЕМ ADMIN_CHAT_ID (уже должен быть int или None из config.py) <----
from config.config import ADMIN_CHAT_ID

# --- Настройка шрифта для PDF ---
PDF_FONT = 'Helvetica' # Шрифт по умолчанию
PDF_FONT_PATH = 'DejaVuSans.ttf' # Путь к файлу шрифта (ожидается в корне проекта)
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', PDF_FONT_PATH))
    PDF_FONT = 'DejaVuSans' # Используем наш шрифт, если он загрузился
    logging.info(f"Шрифт '{PDF_FONT_PATH}' успешно зарегистрирован для PDF.")
except Exception as e:
    logging.warning(
        f"Не найден или не удалось загрузить шрифт '{PDF_FONT_PATH}' ({e}). "
        f"PDF может некорректно отображать кириллицу. Используется '{PDF_FONT}'."
    )
# --- Конец настройки шрифта ---

router = Router()

# --- Проверка ADMIN_CHAT_ID при запуске модуля ---
# Логируем значение, которое будет использоваться для проверки прав
if ADMIN_CHAT_ID is None:
    logging.warning("ADMIN_CHAT_ID не задан или некорректен в config.py. Админ-команды будут недоступны.")
elif not isinstance(ADMIN_CHAT_ID, int):
     logging.error(f"ADMIN_CHAT_ID из config.py не является числом (тип: {type(ADMIN_CHAT_ID)}). Админ-команды не будут работать.")
     ADMIN_CHAT_ID = None # Устанавливаем в None, чтобы фильтр не пропускал
else:
     logging.info(f"ADMIN_CHAT_ID для проверки прав администратора: {ADMIN_CHAT_ID}")


# --- Magic Filter для проверки админа (используем импортированный ADMIN_CHAT_ID) ---
# Используется для /set_prompt и /pdf
ADMIN_FILTER = (F.from_user.id == ADMIN_CHAT_ID) if isinstance(ADMIN_CHAT_ID, int) else (lambda: False)


# --- ЛОГИРУЮЩИЙ PRE-HANDLER УДАЛЕН / ЗАКОММЕНТИРОВАН ---
# @router.message(Command("set_prompt", "chats", "pdf"))
# async def before_admin_cmd_log(message: Message) -> bool:
#     # ... (код удален) ...
#     return False


# --- Основные хэндлеры админских команд ---

@router.message(Command("set_prompt"), ADMIN_FILTER)
async def cmd_set_prompt(message: Message):
    """Устанавливает системный промпт для OpenAI (только админ)."""
    logging.info(f"Пользователь {message.from_user.id} (АДМИН={ADMIN_CHAT_ID}) выполняет /set_prompt")
    new_prompt = message.text.split(maxsplit=1)[1].strip() if ' ' in message.text else ""
    if not new_prompt:
        await message.reply("❗️ Укажите новый шаблон после команды.\nПример: `/set_prompt Сделай краткую сводку:`")
        return
    try:
        await set_setting("summary_prompt", new_prompt)
        await message.reply("✅ Шаблон сводки обновлён.")
    except Exception as e:
        logging.exception(f"Ошибка при сохранении настройки summary_prompt: {e}")
        await message.reply("❌ Не удалось сохранить настройку.")

# ----> CMD_CHATS БЕЗ ФИЛЬТРА В ДЕКОРАТОРЕ, С ВНУТРЕННЕЙ ПРОВЕРКОЙ <----
@router.message(Command("chats")) # <--- Фильтр ADMIN_FILTER убран отсюда
async def cmd_chats(message: Message):
    """Показывает список активных чатов (проверка админа внутри)."""
    # Логгируем вызов хэндлера ДО проверки прав
    logging.info(f"Хэндлер /chats вызван пользователем {message.from_user.id}.")

    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ АДМИНИСТРАТОРА <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /chats запрещен для user {message.from_user.id}. ADMIN_CHAT_ID={ADMIN_CHAT_ID}")
        return # Молча завершаем выполнение хэндлера

    # Если проверка пройдена:
    logging.info(f"Пользователь {message.from_user.id} (АДМИН={ADMIN_CHAT_ID}) прошел проверку и выполняет /chats")
    try:
        logging.info("Запрашиваю список зарегистрированных чатов из БД...")
        chat_ids = await get_registered_chats()
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
                if chat_info.type in ('group', 'supergroup', 'channel'):
                    invite_link = chat_info.invite_link
                    if invite_link:
                        link_part = f" (<a href='{invite_link}'>ссылка</a>)"

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
        # Отправляем частями, если текст слишком длинный
        for i in range(0, len(full_text), MAX_LEN):
            await message.reply(full_text[i:i + MAX_LEN], parse_mode="HTML")
        logging.info("Список чатов успешно отправлен.")

    except Exception as e:
        logging.exception(f"Критическая ошибка при выполнении команды /chats: {e}")
        await message.reply("❌ Произошла ошибка при получении списка чатов.")

# cmd_pdf остается с фильтром ADMIN_FILTER
@router.message(Command("pdf"), ADMIN_FILTER)
async def cmd_pdf(message: Message):
    """Создает PDF с историей сообщений за последние 24ч (только админ)."""
    logging.info(f"Пользователь {message.from_user.id} (АДМИН={ADMIN_CHAT_ID}) выполняет /pdf")
    # ... (остальной код cmd_pdf без изменений) ...
    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip('-').isdigit():
        await message.reply("❗️ Укажите ID чата после команды.\nПример: `/pdf -1001234567890`")
        return
    try:
        chat_id_to_fetch = int(args[1])
    except ValueError:
        await message.reply("❗️ Некорректный ID чата.")
        return
    try:
        since_time = datetime.now(timezone.utc) - timedelta(days=1)
        logging.info(f"Запрос PDF для чата {chat_id_to_fetch} с {since_time.isoformat()}")
        messages_data = await get_messages_for_summary(chat_id_to_fetch, since_time)
        if not messages_data:
            await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
            return
        logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        margin = 40
        textobject = c.beginText()
        textobject.setTextOrigin(margin, height - margin)
        textobject.setFont(PDF_FONT, 8)
        line_height = 10
        for msg in messages_data:
            msg_timestamp = msg["timestamp"]
            if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
            elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
            msg_time_str = msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            sender = msg.get("username", "Unknown User")
            text = msg.get("text", "") or "[пустое сообщение]"
            header = f"[{msg_time_str}] {sender}:"
            lines = simpleSplit(text, PDF_FONT, 8, width - 2 * margin)
            required_lines = 1 + len(lines) + 1
            if textobject.getY() < margin + line_height * required_lines:
                c.drawText(textobject)
                c.showPage()
                textobject = c.beginText(margin, height - margin)
                textobject.setFont(PDF_FONT, 8)
            textobject.textLine(header)
            for line in lines: textobject.textLine(f"  {line}")
            textobject.moveCursor(0, line_height / 2)
        c.drawText(textobject)
        c.save()
        buf.seek(0)
        pdf_filename = f"history_{chat_id_to_fetch}_{since_time.strftime('%Y%m%d')}.pdf"
        logging.info(f"Отправка PDF {pdf_filename} пользователю {message.from_user.id}")
        await message.reply_document(
            InputFile(buf, filename=pdf_filename),
            caption=f"История чата <code>{chat_id_to_fetch}</code> за последние 24 часа."
        )
        logging.info("PDF успешно отправлен.")
    except Exception as e:
        logging.exception(f"Ошибка при создании или отправке PDF для чата {chat_id_to_fetch}: {e}")
        await message.reply("❌ Произошла ошибка при создании PDF.")


# --- Функция отправки сводки ---
# (код send_summary без изменений)
async def send_summary(bot: Bot, chat_id: int):
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    now_aware = datetime.now(timezone.utc)
    since_aware = now_aware - timedelta(days=1)
    logging.info(f"Запрос сообщений для сводки чата {chat_id} с {since_aware}")
    try:
        messages_data = await get_messages_for_summary(chat_id, since=since_aware)
        logging.info(f"📥 Получено сообщений: {len(messages_data)} для чата {chat_id}")
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id}: {e}")
        return
    MIN_MESSAGES_FOR_SUMMARY = 5
    if not messages_data or len(messages_data) < MIN_MESSAGES_FOR_SUMMARY:
        logging.info(f"Недостаточно сообщений ({len(messages_data)}) для сводки в чате {chat_id}.")
        return
    message_blocks = []
    for m in messages_data:
        msg_timestamp = m["timestamp"]
        if msg_timestamp.tzinfo is None: msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc: msg_timestamp = msg_timestamp.astimezone(timezone.utc)
        ts = msg_timestamp.strftime('%H:%M')
        sender = m.get("username", "Unknown")
        text = m.get("text", "") or "[пусто]"
        MAX_MSG_LEN = 1000
        message_blocks.append(f"[{ts}] {sender}: {text[:MAX_MSG_LEN]}")
    default_prompt = "Сделай очень краткую сводку (summary) следующих сообщений в чате за последние 24 часа. Выдели основные темы и ключевые моменты. Ответ дай на русском языке."
    try:
        summary_prompt = await get_setting("summary_prompt") or default_prompt
    except Exception as e:
        logging.exception(f"Ошибка при получении настройки summary_prompt: {e}")
        summary_prompt = default_prompt
    logging.info(f"⏳ Отправляем {len(message_blocks)} блоков сообщений в OpenAI для чата {chat_id}...")
    try:
        summary_text = await summarize_chat(message_blocks, system_prompt=summary_prompt)
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
        await set_setting(f"last_summary_ts_{chat_id}", now_aware.isoformat())
    except Exception as e:
        logging.exception(f"❌ Ошибка при отправке сводки в чат {chat_id}: {e}")


# --- Настройка планировщика ---
# (код setup_scheduler и trigger_all_summaries без изменений)
def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="UTC")
    try:
        scheduler.add_job(
            trigger_all_summaries,
            trigger="cron", hour=21, minute=0,
            args=[bot], id="daily_summaries", replace_existing=True, misfire_grace_time=300
        )
        scheduler.start()
        next_run = scheduler.get_job('daily_summaries').next_run_time
        logging.info(f"Планировщик настроен. Следующий запуск сводок: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if next_run else 'нет'}.")
    except Exception as e:
        logging.exception(f"❌ Не удалось запустить планировщик: {e}")

async def trigger_all_summaries(bot: Bot):
    logging.info("🚀 Запуск ежедневной рассылки сводок...")
    try:
        registered_chats = await get_registered_chats()
        logging.info(f"Найдено {len(registered_chats)} зарегистрированных чатов для сводки.")
        current_time = datetime.now(timezone.utc)
        for chat_id in registered_chats:
            should_send = True
            try:
                last_summary_ts_str = await get_setting(f"last_summary_ts_{chat_id}")
                if last_summary_ts_str:
                    last_summary_time = datetime.fromisoformat(last_summary_ts_str)
                    if last_summary_time.tzinfo is None: last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
                    elif last_summary_time.tzinfo != timezone.utc: last_summary_time = last_summary_time.astimezone(timezone.utc)
                    if current_time - last_summary_time < timedelta(hours=23):
                        should_send = False
                        logging.info(f"Пропуск авто-сводки для чата {chat_id}, последняя была в {last_summary_time.isoformat()}.")
            except ValueError:
                logging.warning(f"Некорректный формат времени последней сводки для чата {chat_id}: {last_summary_ts_str}")
            except Exception as e:
                logging.exception(f"Ошибка при проверке времени последней сводки для чата {chat_id}: {e}")
            if should_send:
                logging.info(f"Запуск задачи сводки для чата {chat_id}...")
                try:
                    await send_summary(bot, chat_id)
                except Exception as e:
                    logging.exception(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")
    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при выполнении trigger_all_summaries: {e}")
    finally:
        logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
