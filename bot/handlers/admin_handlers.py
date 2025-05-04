# --- START OF FILE bot/handlers/admin_handlers.py ---

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

# Убедитесь, что Bot импортирован
from aiogram import Router, Bot
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
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID

# Для type hinting, чтобы избежать циклического импорта с main.py, если он понадобится
# if TYPE_CHECKING:
#     from aiogram import Dispatcher

# --- Настройка шрифта для PDF ---
PDF_FONT = 'Helvetica' # Шрифт по умолчанию
PDF_FONT_PATH = 'DejaVuSans.ttf' # Путь к файлу шрифта (в корне проекта)
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

# Проверяем ADMIN_CHAT_ID при инициализации модуля
if ADMIN_CHAT_ID is None:
    logging.warning("ADMIN_CHAT_ID не задан. Админ-команды будут недоступны.")

# Фильтр для проверки, является ли пользователь админом
# Можно использовать встроенный MagicFilter F.from_user.id == ADMIN_CHAT_ID
# Или отдельную функцию/класс-фильтр
def is_admin(message: Message) -> bool:
    return ADMIN_CHAT_ID is not None and message.from_user.id == ADMIN_CHAT_ID

@router.message(Command("set_prompt"), is_admin) # Используем фильтр
async def cmd_set_prompt(message: Message):
    """Устанавливает системный промпт для OpenAI (только админ)."""
    # Извлекаем аргументы команды правильно
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


@router.message(Command("chats"), is_admin) # Используем фильтр
async def cmd_chats(message: Message):
    """Показывает список активных чатов (только админ)."""
    try:
        chat_ids = await get_registered_chats()
        if not chat_ids:
            await message.reply("Нет зарегистрированных чатов.")
            return

        lines = ["<b>Активные чаты:</b>"]
        for cid in chat_ids:
            try:
                chat_info = await message.bot.get_chat(cid)
                title = chat_info.title or chat_info.full_name or f"ID: {cid}"
                link = f" (<a href='{chat_info.invite_link}'>ссылка</a>)" if chat_info.invite_link else ""
                lines.append(f"• {title} (<code>{cid}</code>){link}")
            except Exception as e:
                logging.warning(f"Не удалось получить информацию о чате {cid}: {e}")
                lines.append(f"• ID: <code>{cid}</code> (нет доступа?)")

        full_text = "\n".join(lines)
        MAX_LEN = 4096
        # Отправляем частями, если нужно
        for i in range(0, len(full_text), MAX_LEN):
            await message.reply(full_text[i:i + MAX_LEN], parse_mode="HTML")

    except Exception as e:
        logging.exception(f"Ошибка при выполнении команды /chats: {e}")
        await message.reply("❌ Произошла ошибка при получении списка чатов.")


@router.message(Command("pdf"), is_admin) # Используем фильтр
async def cmd_pdf(message: Message):
    """Создает PDF с историей сообщений за последние 24ч (только админ)."""
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
        logging.info(f"Запрос PDF для чата {chat_id_to_fetch} с {since_time}")
        messages_data = await get_messages_for_summary(chat_id_to_fetch, since_time)

        if not messages_data:
            await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
            return

        logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        textobject = c.beginText()
        textobject.setTextOrigin(40, height - 40)
        textobject.setFont(PDF_FONT, 8)
        line_height = 10

        for msg in messages_data:
            msg_timestamp = msg["timestamp"]
            if msg_timestamp.tzinfo is None:
                msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
            elif msg_timestamp.tzinfo != timezone.utc:
                msg_timestamp = msg_timestamp.astimezone(timezone.utc)

            msg_time_str = msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            sender = msg.get("username", "Unknown User")
            text = msg.get("text", "") or "[пустое сообщение]" # Обработка пустого текста

            header = f"[{msg_time_str}] {sender}:"
            # Используем simpleSplit для переноса длинных строк
            lines = simpleSplit(text, PDF_FONT, 8, width - 80)

            # Предварительная оценка места + запас
            required_lines = 1 + len(lines) + 1 # header + text + space
            if textobject.getY() < 40 + line_height * required_lines:
                c.drawText(textobject)
                c.showPage()
                textobject = c.beginText(40, height - 40)
                textobject.setFont(PDF_FONT, 8)

            textobject.textLine(header)
            for line in lines:
                 textobject.textLine(f"  {line}")
            textobject.moveCursor(0, line_height / 2) # Отступ

        c.drawText(textobject)
        c.save()
        buf.seek(0)

        pdf_filename = f"history_{chat_id_to_fetch}_{since_time.strftime('%Y%m%d')}.pdf"
        await message.reply_document(
            InputFile(buf, filename=pdf_filename),
            caption=f"История чата <code>{chat_id_to_fetch}</code> за последние 24 часа."
        )

    except Exception as e:
        logging.exception(f"Ошибка при создании PDF для чата {chat_id_to_fetch}: {e}")
        await message.reply("❌ Произошла ошибка при создании PDF.")


# Этот хэндлер должен быть в user_handlers.py, чтобы не требовать админ прав
# @router.message(Command("summary"))
# async def cmd_summary_trigger(message: Message):
#     """Создаёт саммари по сообщениям за 24 часа."""
#     # ...


async def send_summary(bot: Bot, chat_id: int):
    """Собирает сообщения за 24 часа, генерирует и отправляет сводку."""
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    now_aware = datetime.now(timezone.utc)
    since_aware = now_aware - timedelta(days=1)

    logging.info(f"Запрос сообщений для сводки чата {chat_id} с {since_aware}")
    try:
        messages_data = await get_messages_for_summary(chat_id, since=since_aware)
        logging.info(f"📥 Получено сообщений: {len(messages_data)} для чата {chat_id}")
    except Exception as e:
        logging.exception(f"❌ Ошибка при получении сообщений для сводки чата {chat_id}: {e}")
        # Не спамим в чат, если ошибка на нашей стороне
        # await bot.send_message(chat_id, "⚠️ Не удалось получить сообщения для создания сводки.")
        return

    MIN_MESSAGES_FOR_SUMMARY = 5 # Можно вынести в config.py
    if not messages_data or len(messages_data) < MIN_MESSAGES_FOR_SUMMARY:
        logging.info(f"Недостаточно сообщений ({len(messages_data)}) для сводки в чате {chat_id}.")
        # Не уведомляем чат об этом, чтобы не спамить
        return

    message_blocks = []
    for m in messages_data:
        msg_timestamp = m["timestamp"]
        if msg_timestamp.tzinfo is None:
            msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc:
            msg_timestamp = msg_timestamp.astimezone(timezone.utc)
        ts = msg_timestamp.strftime('%H:%M')
        sender = m.get("username", "Unknown")
        text = m.get("text", "") or "[пусто]"
        MAX_MSG_LEN = 1000 # Лимит длины одного сообщения для OpenAI
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
        # Уведомляем чат об ошибке, но без деталей
        try: await bot.send_message(chat_id, "⚠️ Произошла ошибка при генерации сводки.")
        except Exception: pass
        return

    if not summary_text:
        logging.warning(f"OpenAI вернул пустую сводку для чата {chat_id}.")
        # Не уведомляем, если модель просто ничего не вернула
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


def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик для ежедневной отправки сводок."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    try:
        scheduler.add_job(
            trigger_all_summaries,
            trigger="cron",
            hour=21, # 21:00 UTC
            minute=0,
            args=[bot],
            id="daily_summaries",
            replace_existing=True,
            misfire_grace_time=300 # Даем 5 минут на запуск, если пропустили
        )
        scheduler.start()
        logging.info(f"Планировщик настроен на ежедневный запуск сводок в {scheduler.get_job('daily_summaries').next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
    except Exception as e:
        logging.exception(f"❌ Не удалось запустить планировщик: {e}")


async def trigger_all_summaries(bot: Bot):
    """Запускает отправку сводок для всех зарегистрированных чатов."""
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
                    if last_summary_time.tzinfo is None:
                        last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
                    elif last_summary_time.tzinfo != timezone.utc:
                        last_summary_time = last_summary_time.astimezone(timezone.utc)

                    # Не отправляем, если последняя сводка была менее 23 часов назад
                    if current_time - last_summary_time < timedelta(hours=23):
                        should_send = False
                        logging.info(f"Пропуск автоматической сводки для чата {chat_id}, т.к. последняя была в {last_summary_time.isoformat()}.")
            except ValueError:
                logging.warning(f"Некорректный формат времени последней сводки для чата {chat_id}: {last_summary_ts_str}")
            except Exception as e:
                logging.exception(f"Ошибка при проверке времени последней сводки для чата {chat_id}: {e}")

            if should_send:
                logging.info(f"Запуск задачи сводки для чата {chat_id}...")
                try:
                    # Запускаем последовательно, чтобы не перегружать API/DB
                    await send_summary(bot, chat_id)
                except Exception as e:
                    logging.exception(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")
            # else: # Лог пропуска уже есть выше
            #    logging.info(f"Сводка для чата {chat_id} пропущена по условию времени.")

    except Exception as e:
        logging.exception(f"❌ Критическая ошибка при выполнении trigger_all_summaries: {e}")
    finally:
        logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
