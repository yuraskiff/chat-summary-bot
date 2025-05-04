# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Dict # Добавим типы для ясности

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
     ADMIN_CHAT_ID = None # Устанавливаем None, чтобы проверка ниже работала
else:
     logging.info(f"ADMIN_CHAT_ID для проверки прав администратора: {ADMIN_CHAT_ID}")

# --- Хэндлеры админских команд с внутренней проверкой прав ---

@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    """Устанавливает системный промпт для OpenAI (проверка админа внутри)."""
    logging.debug(f"Хэндлер /set_prompt вызван пользователем {message.from_user.id}.")
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /set_prompt запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /set_prompt")

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

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """Показывает список активных чатов (проверка админа внутри)."""
    logging.debug(f"Хэндлер /chats вызван пользователем {message.from_user.id}.")
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /chats запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /chats")
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
                # Пытаемся получить ссылку для групп/каналов
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
    # ----> ЯВНАЯ ПРОВЕРКА ПРАВ <----
    if not isinstance(ADMIN_CHAT_ID, int) or message.from_user.id != ADMIN_CHAT_ID:
        logging.warning(f"Доступ к /pdf запрещен для user {message.from_user.id}.")
        return
    logging.info(f"Пользователь {message.from_user.id} (АДМИН) прошел проверку и выполняет /pdf")

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
        messages_data: List[Dict] = await get_messages_for_summary(chat_id_to_fetch, since_time)

        if not messages_data:
            await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
            return

        logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
        # --- Генерация PDF ---
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        margin = 40
        textobject = c.beginText()
        textobject.setTextOrigin(margin, height - margin)
        textobject.setFont(PDF_FONT, 8)
        line_height = 10

        for msg in messages_data:
            msg_timestamp: datetime = msg["timestamp"]
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
        # --- Конец генерации PDF ---

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


# --- Функция отправки сводки (вызывается /summary и планировщиком) ---
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

    MIN_MESSAGES_FOR_SUMMARY = 5 # Можно вынести в config.py
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
        MAX_MSG_LEN = 1000 # Лимит длины одного сообщения для OpenAI
        message_blocks.append(f"[{ts}] {sender}: {text[:MAX_MSG_LEN]}")

    default_prompt = "Сделай очень краткую сводку (summary) следующих сообщений в чате за последние 24 часа. Выдели основные темы и ключевые моменты. Ответ дай на русском языке."
    summary_prompt = default_prompt # Значение по умолчанию
    try:
        # Пытаемся получить кастомный промпт из настроек
        custom_prompt = await get_setting("summary_prompt")
        if custom_prompt:
            summary_prompt = custom_prompt
            logging.info(f"Используется кастомный промпт для чата {chat_id}.")
        else:
            logging.info(f"Используется дефолтный промпт для чата {chat_id}.")
    except Exception as e:
        logging.exception(f"Ошибка при получении настройки summary_prompt для чата {chat_id}. Используется дефолтный промпт.")

    logging.info(f"⏳ Отправляем {len(message_blocks)} блоков сообщений в OpenAI для чата {chat_id}...")
    summary_text: Optional[str] = None
    try:
        summary_text = await summarize_chat(message_blocks, system_prompt=summary_prompt)
    except Exception as e:
        logging.exception(f"❌ Ошибка при запросе к OpenAI для чата {chat_id}: {e}")
        try: await bot.send_message(chat_id, "⚠️ Произошла ошибка при генерации сводки.")
        except Exception: pass # Игнорируем ошибку отправки, если бот не может писать в чат
        return

    if not summary_text:
        logging.warning(f"OpenAI вернул пустую сводку для чата {chat_id}.")
        # Не отправляем уведомление об этом
        return

    try:
        full_summary_text = f"📝 <b>Сводка за последние 24 часа:</b>\n\n{summary_text}"
        MAX_LEN = 4096
        # Отправляем частями, если нужно
        for i in range(0, len(full_summary_text), MAX_LEN):
            await bot.send_message(chat_id, full_summary_text[i:i + MAX_LEN], parse_mode="HTML")

        # Используем logging.info вместо logging.success
        logging.info(f"✅ Сводка успешно отправлена в чат {chat_id}")
        # Сохраняем время последней успешной сводки
        await set_setting(f"last_summary_ts_{chat_id}", now_aware.isoformat())
    except Exception as e:
        logging.exception(f"❌ Ошибка при отправке сводки в чат {chat_id}: {e}")


# --- Настройка и запуск планировщика ---
def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик для ежедневной отправки сводок."""
    scheduler = AsyncIOScheduler(timezone="UTC") # Работаем в UTC
    try:
        scheduler.add_job(
            trigger_all_summaries, # Функция для выполнения
            trigger="cron",        # Тип триггера - по расписанию
            hour=21,               # Час UTC (например, 21:00 UTC = 00:00 GMT+3)
            minute=0,              # Минута
            args=[bot],            # Аргументы для функции trigger_all_summaries
            id="daily_summaries",  # Уникальный ID задачи
            replace_existing=True, # Заменять задачу, если она уже есть
            misfire_grace_time=300 # Допустимое время опоздания запуска (5 минут)
        )
        scheduler.start()
        # Логируем время следующего запуска
        next_run = scheduler.get_job('daily_summaries').next_run_time
        if next_run:
            logging.info(f"Планировщик настроен. Следующий запуск сводок: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
        else:
             logging.warning("Не удалось определить время следующего запуска планировщика.")
    except Exception as e:
        logging.exception(f"❌ Не удалось настроить или запустить планировщик: {e}")


async def trigger_all_summaries(bot: Bot):
    """Запускает отправку сводок для всех зарегистрированных чатов."""
    logging.info("🚀 Запуск ежедневной рассылки сводок по расписанию...")
    try:
        registered_chats: List[int] = await get_registered_chats()
        logging.info(f"Найдено {len(registered_chats)} зарегистрированных чатов для отправки сводки.")
        if not registered_chats:
            logging.info("Нет зарегистрированных чатов, рассылка не требуется.")
            return

        current_time = datetime.now(timezone.utc)

        for chat_id in registered_chats:
            should_send = True
            try:
                # Проверяем время последней отправленной сводки для этого чата
                last_summary_ts_str = await get_setting(f"last_summary_ts_{chat_id}")
                if last_summary_ts_str:
                    try:
                        last_summary_time = datetime.fromisoformat(last_summary_ts_str)
                        # Приводим к aware UTC для корректного сравнения
                        if last_summary_time.tzinfo is None: last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
                        elif last_summary_time.tzinfo != timezone.utc: last_summary_time = last_summary_time.astimezone(timezone.utc)

                        # Не отправляем, если последняя сводка была менее 23 часов назад
                        if current_time - last_summary_time < timedelta(hours=23):
                            should_send = False
                            logging.info(f"Пропуск автоматической сводки для чата {chat_id}, т.к. последняя была отправлена недавно ({last_summary_time.isoformat()}).")
                    except ValueError:
                        logging.warning(f"Некорректный формат времени '{last_summary_ts_str}' последней сводки для чата {chat_id}. Отправляем сводку.")
            except Exception as e:
                # Логируем ошибку проверки, но все равно пытаемся отправить сводку
                logging.exception(f"Ошибка при проверке времени последней сводки для чата {chat_id}. Попытка отправки сводки...")

            if should_send:
                logging.info(f"Запуск задачи отправки сводки для чата {chat_id}...")
                try:
                    # Выполняем отправку последовательно для каждого чата
                    await send_summary(bot, chat_id)
                except Exception as e:
                    # Логируем ошибку для конкретного чата, но продолжаем для остальных
                    logging.exception(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")
            # else: # Лог о пропуске уже есть выше

    except Exception as e:
        # Логируем критическую ошибку в самой функции рассылки
        logging.exception(f"❌ Критическая ошибка при выполнении trigger_all_summaries: {e}")
    finally:
        logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
