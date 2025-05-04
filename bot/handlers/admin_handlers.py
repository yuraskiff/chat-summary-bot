# --- START OF FILE admin_handlers.py ---

import io
import logging # Добавим логирование для лучшей отладки
from datetime import datetime, timedelta, timezone

# Убедитесь, что Bot и Dispatcher импортированы (Dispatcher может не понадобиться здесь)
from aiogram import Router, Bot, Dispatcher
from aiogram.types import Message, InputFile
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit # Для переноса строк в PDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from db.db import (
    get_registered_chats,
    get_messages_for_summary,
    get_setting,
    set_setting
)
from api_clients.openrouter import summarize_chat
from config.config import ADMIN_CHAT_ID # Убедитесь, что ADMIN_CHAT_ID правильно загружен из конфига/env

# Попытка зарегистрировать шрифт, поддерживающий кириллицу (нужен файл DejaVuSans.ttf)
try:
    # Укажите полный путь к шрифту, если он не в корневой папке
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    PDF_FONT = 'DejaVuSans'
    logging.info("Шрифт DejaVuSans.ttf успешно зарегистрирован для PDF.")
except Exception as e:
    logging.warning(f"Не найден или не удалось загрузить шрифт DejaVuSans.ttf ({e}), PDF может некорректно отображать кириллицу.")
    PDF_FONT = 'Helvetica' # Fallback

router = Router()

# Преобразуем ADMIN_CHAT_ID в int один раз для сравнения
try:
    ADMIN_ID = int(ADMIN_CHAT_ID)
except ValueError:
    logging.error(f"Некорректное значение ADMIN_CHAT_ID: '{ADMIN_CHAT_ID}'. Установите правильный ID администратора.")
    ADMIN_ID = None # Или установите значение по умолчанию, или прервите работу

@router.message(Command("set_prompt"))
async def cmd_set_prompt(message: Message):
    """Устанавливает системный промпт для OpenAI (только админ)."""
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        logging.warning(f"Попытка доступа к /set_prompt от user {message.from_user.id}")
        return # Молча игнорируем не-админов

    # Извлекаем аргументы команды правильно
    new_prompt = message.text.split(maxsplit=1)[1].strip() if ' ' in message.text else ""
    if not new_prompt:
        await message.reply("❗️ Укажите новый шаблон после команды.\nПример: `/set_prompt Сделай краткую сводку:`")
        return

    await set_setting("summary_prompt", new_prompt)
    await message.reply("✅ Шаблон сводки обновлён.")

@router.message(Command("chats"))
async def cmd_chats(message: Message):
    """Показывает список активных чатов (только админ)."""
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        logging.warning(f"Попытка доступа к /chats от user {message.from_user.id}")
        return

    chat_ids = await get_registered_chats()
    if not chat_ids:
        await message.reply("Нет зарегистрированных чатов.")
        return

    lines = ["<b>Активные чаты:</b>"]
    for cid in chat_ids:
        try:
            # Пытаемся получить информацию о чате
            chat_info = await message.bot.get_chat(cid)
            title = chat_info.title or chat_info.full_name or f"ID: {cid}"
            link = chat_info.invite_link or "" # Попробуем получить ссылку
            lines.append(f"• {title} (<code>{cid}</code>) {link}")
        except Exception as e:
            # Если бот не может получить инфо (удалили из чата?), просто покажем ID
            logging.warning(f"Не удалось получить информацию о чате {cid}: {e}")
            lines.append(f"• ID: <code>{cid}</code> (нет доступа?)")

    # Разбиваем сообщение, если оно слишком длинное для Telegram
    full_text = "\n".join(lines)
    MAX_LEN = 4096
    if len(full_text) > MAX_LEN:
        for i in range(0, len(full_text), MAX_LEN):
            await message.reply(full_text[i:i + MAX_LEN])
    else:
        await message.reply(full_text)


@router.message(Command("pdf"))
async def cmd_pdf(message: Message):
    """Создает PDF с историей сообщений за последние 24ч (только админ)."""
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        logging.warning(f"Попытка доступа к /pdf от user {message.from_user.id}")
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip('-').isdigit(): # Проверяем, что второй аргумент - число (возможно, отрицательное для ID чата)
        await message.reply("❗️ Укажите ID чата после команды.\nПример: `/pdf -1001234567890`")
        return

    try:
        chat_id_to_fetch = int(args[1])
    except ValueError:
        await message.reply("❗️ Некорректный ID чата.")
        return

    # Получаем сообщения за последние 24 часа
    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    logging.info(f"Запрос PDF для чата {chat_id_to_fetch} с {since_time}")
    messages_data = await get_messages_for_summary(chat_id_to_fetch, since_time)

    if not messages_data:
        await message.reply(f"Сообщений в чате <code>{chat_id_to_fetch}</code> за последние 24 часа не найдено.")
        return

    logging.info(f"Найдено {len(messages_data)} сообщений для PDF в чате {chat_id_to_fetch}.")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter # Размеры страницы

    # Настройки текста
    textobject = c.beginText()
    textobject.setTextOrigin(40, height - 40) # Отступы от краев
    textobject.setFont(PDF_FONT, 8) # Используем зарегистрированный шрифт
    line_height = 10 # Межстрочный интервал

    for msg in messages_data:
        # Форматируем время (asyncpg возвращает aware datetime)
        # Убедимся, что время в UTC перед форматированием
        msg_timestamp = msg["timestamp"]
        if msg_timestamp.tzinfo is None:
             msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc:
             msg_timestamp = msg_timestamp.astimezone(timezone.utc)

        msg_time_str = msg_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        sender = msg.get("username", "Unknown User")
        text = msg.get("text", "")

        header = f"[{msg_time_str}] {sender}:"
        # Используем simpleSplit для переноса длинных строк
        lines = simpleSplit(text or "", textobject.getFontName(), textobject.getFontSize(), width - 80) # Отступы по 40 с каждой стороны

        # Проверка на конец страницы перед выводом заголовка
        if textobject.getY() < 40 + line_height * (len(lines) + 1): # Предварительная оценка места
             c.drawText(textobject)
             c.showPage()
             textobject = c.beginText(40, height - 40)
             textobject.setFont(PDF_FONT, 8)

        # Выводим заголовок
        textobject.textLine(header)

        # Выводим строки текста сообщения
        for line in lines:
             # Проверка на конец страницы перед выводом строки
             if textobject.getY() < 40 + line_height:
                 c.drawText(textobject)
                 c.showPage()
                 textobject = c.beginText(40, height - 40)
                 textobject.setFont(PDF_FONT, 8)
             textobject.textLine(f"  {line}")

        # Небольшой отступ между сообщениями
        textobject.moveCursor(0, line_height / 2)
        if textobject.getY() < 40: # Проверка на конец страницы
             c.drawText(textobject)
             c.showPage()
             textobject = c.beginText(40, height - 40)
             textobject.setFont(PDF_FONT, 8)


    c.drawText(textobject)
    c.save()
    buf.seek(0)

    # Отправляем документ
    pdf_filename = f"history_{chat_id_to_fetch}_{since_time.strftime('%Y%m%d')}.pdf"
    await message.reply_document(InputFile(buf, filename=pdf_filename), caption=f"История чата <code>{chat_id_to_fetch}</code> за последние 24 часа.")


@router.message(Command("summary"))
async def cmd_summary_trigger(message: Message):
    """
    Создаёт саммари по сообщениям за последние 24 часа.
    Доступна всем в чате, где есть бот.
    """
    chat_id = message.chat.id
    logging.info(f"Запрошена сводка командой /summary для чата {chat_id}")
    await send_summary(message.bot, chat_id)


async def send_summary(bot: Bot, chat_id: int):
    """
    Собирает сообщения за последние 24 часа, генерирует и отправляет сводку.
    """
    logging.info(f"Начало генерации сводки для чата {chat_id}")
    now_aware = datetime.now(timezone.utc) # Получаем текущее время как aware UTC

    # Вычисляем время начала периода (24 часа назад) как aware UTC
    since_aware = now_aware - timedelta(days=1)

    logging.info(f"Запрос сообщений для сводки чата {chat_id} с {since_aware}")
    try:
        # Передаем aware datetime в функцию БД
        messages_data = await get_messages_for_summary(chat_id, since=since_aware)
        logging.info(f"📥 Получено сообщений: {len(messages_data)} для чата {chat_id}")
    except Exception as e:
        logging.error(f"❌ Ошибка при получении сообщений для сводки чата {chat_id}: {e}")
        try:
            await bot.send_message(chat_id, "⚠️ Не удалось получить сообщения для создания сводки.")
        except Exception as send_error:
            logging.error(f"❌ Не удалось отправить сообщение об ошибке в чат {chat_id}: {send_error}")
        return

    # Минимальное количество сообщений для сводки (можно вынести в конфиг)
    MIN_MESSAGES_FOR_SUMMARY = 5
    if not messages_data or len(messages_data) < MIN_MESSAGES_FOR_SUMMARY:
        logging.info(f"Недостаточно сообщений ({len(messages_data)}) для сводки в чате {chat_id}.")
        # Можно раскомментировать, если хотите уведомлять об этом
        # try:
        #     await bot.send_message(chat_id, f"Сообщений за последние 24 часа ({len(messages_data)}) недостаточно для сводки (нужно {MIN_MESSAGES_FOR_SUMMARY}).")
        # except Exception as send_error:
        #      logging.error(f"❌ Не удалось отправить сообщение об отсутствии сообщений в чат {chat_id}: {send_error}")
        return

    # Формируем текст для OpenAI
    # Добавляем временные метки для лучшего контекста
    message_blocks = []
    for m in messages_data:
        # Убедимся, что время в UTC перед форматированием
        msg_timestamp = m["timestamp"]
        if msg_timestamp.tzinfo is None:
             msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)
        elif msg_timestamp.tzinfo != timezone.utc:
             msg_timestamp = msg_timestamp.astimezone(timezone.utc)

        ts = msg_timestamp.strftime('%H:%M') # Время в UTC
        sender = m.get("username", "Unknown")
        text = m.get("text", "")
        # Пропускаем слишком длинные сообщения, чтобы не превышать лимиты модели
        MAX_MSG_LEN = 1000
        message_blocks.append(f"[{ts}] {sender}: {text[:MAX_MSG_LEN]}")

    # Получаем системный промпт из настроек (если есть)
    default_prompt = "Сделай очень краткую сводку (summary) следующих сообщений в чате за последние 24 часа. Выдели основные темы и ключевые моменты. Ответ дай на русском языке."
    summary_prompt = await get_setting("summary_prompt") or default_prompt

    logging.info(f"⏳ Отправляем {len(message_blocks)} блоков сообщений в OpenAI для чата {chat_id}...")

    try:
        # Вызываем функцию для запроса к OpenAI (из api_clients/openrouter.py)
        summary_text = await summarize_chat(message_blocks, system_prompt=summary_prompt)
    except Exception as e:
        logging.error(f"❌ Ошибка при запросе к OpenAI для чата {chat_id}: {e}")
        try:
            # Не отправляем детали ошибки пользователю, только в лог
            await bot.send_message(chat_id, f"⚠️ Произошла ошибка при генерации сводки.")
        except Exception as send_error:
            logging.error(f"❌ Не удалось отправить сообщение об ошибке OpenAI в чат {chat_id}: {send_error}")
        return

    if not summary_text:
        logging.warning(f"OpenAI вернул пустую сводку для чата {chat_id}.")
        try:
            await bot.send_message(chat_id, "Не удалось сгенерировать сводку (получен пустой ответ).")
        except Exception as send_error:
             logging.error(f"❌ Не удалось отправить сообщение о пустой сводке в чат {chat_id}: {send_error}")
        return

    # Отправляем готовую сводку
    try:
        # Разбиваем сообщение, если оно слишком длинное
        full_summary_text = f"📝 <b>Сводка за последние 24 часа:</b>\n\n{summary_text}"
        MAX_LEN = 4096
        if len(full_summary_text) > MAX_LEN:
            for i in range(0, len(full_summary_text), MAX_LEN):
                await bot.send_message(chat_id, full_summary_text[i:i + MAX_LEN])
        else:
            await bot.send_message(chat_id, full_summary_text)

        logging.success(f"✅ Сводка успешно отправлена в чат {chat_id}")
        # Сохраняем время последней успешной сводки (используем aware UTC)
        await set_setting(f"last_summary_ts_{chat_id}", now_aware.isoformat())
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке сводки в чат {chat_id}: {e}")


# ----> ИЗМЕНЕНА СИГНАТУРА: ПРИНИМАЕТ bot: Bot <----
def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик для ежедневной отправки сводок."""
    scheduler = AsyncIOScheduler(timezone="UTC") # Используем UTC для планировщика
    # Запускаем каждый день в 21:00 UTC (00:00 Europe/Tallinn или 23:00 МСК летом)
    scheduler.add_job(
        trigger_all_summaries, # Функция, которую нужно запустить
        trigger="cron",
        hour=21,
        minute=0,
        # ----> ИЗМЕНЕНИЕ ЗДЕСЬ: ПЕРЕДАЕМ bot <----
        args=[bot], # Передаем объект бота в функцию
        id="daily_summaries", # Уникальный ID задачи
        replace_existing=True # Заменять задачу, если она уже существует с таким ID
    )
    try:
        scheduler.start()
        # Планировщик больше не сохраняется в dp, если он не нужен для внешнего управления
        logging.info(f"Планировщик настроен на ежедневный запуск сводок в 21:00 UTC.")
    except Exception as e:
        logging.error(f"❌ Не удалось запустить планировщик: {e}")


async def trigger_all_summaries(bot: Bot):
    """Запускает отправку сводок для всех зарегистрированных чатов."""
    logging.info("🚀 Запуск ежедневной рассылки сводок...")
    registered_chats = await get_registered_chats()
    logging.info(f"Найдено {len(registered_chats)} зарегистрированных чатов для сводки.")
    current_time = datetime.now(timezone.utc) # Получаем текущее время один раз

    for chat_id in registered_chats:
        # Проверим, не было ли сводки недавно (например, вызванной вручную)
        last_summary_ts_str = await get_setting(f"last_summary_ts_{chat_id}")
        should_send = True
        if last_summary_ts_str:
            try:
                last_summary_time = datetime.fromisoformat(last_summary_ts_str)
                # Убедимся, что время aware и в UTC
                if last_summary_time.tzinfo is None:
                    last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
                elif last_summary_time.tzinfo != timezone.utc:
                    last_summary_time = last_summary_time.astimezone(timezone.utc)

                # Не отправляем, если последняя сводка была менее 23 часов назад
                # Сравниваем aware с aware
                if current_time - last_summary_time < timedelta(hours=23):
                    should_send = False
                    logging.info(f"Пропуск автоматической сводки для чата {chat_id}, т.к. последняя была недавно ({last_summary_time}).")
            except ValueError:
                logging.warning(f"Некорректный формат времени последней сводки для чата {chat_id}: {last_summary_ts_str}")

        if should_send:
            logging.info(f"Запуск задачи сводки для чата {chat_id}...")
            try:
                # Запускаем задачу отправки сводки для каждого чата
                # Используем create_task для асинхронного запуска, чтобы не блокировать цикл
                # asyncio.create_task(send_summary(bot, chat_id))
                # ИЛИ если хотите последовательно:
                await send_summary(bot, chat_id)
            except Exception as e:
                # Логируем ошибку для конкретного чата, но продолжаем для других
                logging.error(f"❌ Исключение при вызове send_summary для чата {chat_id} в планировщике: {e}")
        else:
             # Логгируем пропуск, если не отправляем
             logging.info(f"Сводка для чата {chat_id} пропущена по условию времени.")

    logging.info("🏁 Ежедневная рассылка сводок завершена.")

# --- END OF FILE admin_handlers.py ---
