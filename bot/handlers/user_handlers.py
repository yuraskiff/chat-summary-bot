# --- START OF FILE user_handlers.py ---

import logging
from datetime import timezone # Импортируем для работы с временными метками

from aiogram import Router, F # <--- Добавлен импорт F для Magic Filter
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

# Импортируем функции из других модулей
from db.db import save_message, register_chat
# Импортируем функцию для вызова сводки
from bot.handlers.admin_handlers import send_summary

router = Router()

# ----> ОБРАБОТЧИК КОМАНДЫ /start <----
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start. Отправляет приветственное сообщение."""
    user_name = message.from_user.full_name
    # Формируем приветственное сообщение с HTML-разметкой
    # Используем безопасные плейсхолдеры без < >
    text = (
        f"Привет, <b>{user_name}</b>!\n\n"
        f"Я бот для создания кратких сводок (summary) в групповых чатах.\n\n"
        f"<b>Как использовать:</b>\n"
        f"1. Добавьте меня в любую группу.\n"
        f"2. Я буду автоматически сохранять сообщения.\n"
        f"3. Раз в сутки (около полуночи по времени сервера UTC) я буду присылать сводку сообщений за последние 24 часа.\n"
        f"4. Вы также можете запросить сводку за последние 24 часа в любое время командой <code>/summary</code> прямо в группе.\n\n"
        f"Для администратора бота доступны дополнительные команды (в личном чате с ботом или в группе): "
        f"<code>/chats</code>, <code>/pdf ID_ЧАТА</code>, <code>/set_prompt ТЕКСТ_ПРОМПТА</code>."
    )
    try:
        # Отправляем ответ с указанием parse_mode
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        # Логируем ошибку, но не сообщаем пользователю, если это просто /start
        logging.exception(f"Ошибка при отправке ответа на /start пользователю {message.from_user.id}: {e}")

# ----> ОБРАБОТЧИК КОМАНДЫ /summary <----
# Этот обработчик доступен всем
@router.message(Command("summary"))
async def cmd_summary(message: Message):
    """Позволяет любому участнику чата вызвать сводку за последние 24 часа."""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "unknown"
    logging.info(f"Запрошена сводка командой /summary для чата {chat_id} пользователем {user_id}")
    try:
        # Вызываем общую функцию отправки сводки из admin_handlers
        await send_summary(message.bot, chat_id)
    except Exception as e:
        logging.exception(f"Критическая ошибка при обработке /summary для чата {chat_id}: {e}")
        try:
            # Отправляем сообщение об ошибке пользователю
            await message.reply("❌ Произошла непредвиденная ошибка при запросе сводки.")
        except Exception as send_error:
            # Логируем, если даже сообщение об ошибке отправить не удалось
             logging.error(f"Не удалось отправить сообщение об ошибке /summary в чат {chat_id}: {send_error}")


# ----> ОБРАБОТЧИК ОБЫЧНЫХ ТЕКСТОВЫХ СООБЩЕНИЙ <----
# Ловит только сообщения с текстом, который НЕ начинается с "/"
@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """
    Сохраняет ТОЛЬКО обычные текстовые сообщения (не команды) в БД.
    """
    # Не обрабатываем сообщения без отправителя
    if not message.from_user:
        return

    # Регистрируем чат (на случай, если бота добавили без события my_chat_member)
    await register_chat(message.chat.id)

    # Сохраняем текст
    text_to_save = message.text
    sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"
    timestamp_to_save = message.date
    if timestamp_to_save.tzinfo is None: timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
    elif timestamp_to_save.tzinfo != timezone.utc: timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)

    try:
        await save_message(
            chat_id=message.chat.id,
            username=sender_name,
            text=text_to_save,
            timestamp=timestamp_to_save
        )
    except Exception as e:
        # Логируем ошибку сохранения, но не беспокоим пользователя
        logging.exception(f"Ошибка при сохранении ТЕКСТОВОГО сообщения в БД для чата {message.chat.id}: {e}")


# ----> ОБРАБОТЧИК ПОДПИСЕЙ К МЕДИА (CAPTION) <----
# Ловит только сообщения, у которых есть подпись (caption)
@router.message(F.caption)
async def handle_caption_message(message: Message):
    """Сохраняет ТОЛЬКО подписи к медиа (фото, видео, документы) в БД."""
    # Не обрабатываем сообщения без отправителя
    if not message.from_user:
        return

    # Регистрируем чат
    await register_chat(message.chat.id)

    # Сохраняем подпись
    text_to_save = message.caption # Берем caption
    sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"
    timestamp_to_save = message.date
    if timestamp_to_save.tzinfo is None: timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
    elif timestamp_to_save.tzinfo != timezone.utc: timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)

    try:
        await save_message(
            chat_id=message.chat.id,
            username=sender_name,
            text=text_to_save, # Сохраняем подпись как текст
            timestamp=timestamp_to_save
        )
    except Exception as e:
        logging.exception(f"Ошибка при сохранении CAPTION сообщения в БД для чата {message.chat.id}: {e}")

# Важно: Нет общего @router.message() без фильтров, чтобы не перехватывать команды из других роутеров.

# --- END OF FILE user_handlers.py ---
