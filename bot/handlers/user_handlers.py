# --- START OF FILE user_handlers.py ---

import logging
from datetime import timezone # Импортируем для работы с временными метками

from aiogram import Router, F # <--- Убедитесь, что F импортирован
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

# Импортируем функции из других модулей
from db.db import save_message, register_chat
# Импортируем функцию для вызова сводки
from bot.handlers.admin_handlers import send_summary # Этот импорт нужен для /summary

router = Router()

# ----> ОБРАБОТЧИК КОМАНДЫ /start <----
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start. Отправляет приветственное сообщение."""
    user_name = message.from_user.full_name
    text = (
        f"Привет, <b>{user_name}</b>!\n\n"
        f"Я бот для создания кратких сводок (summary) в групповых чатах.\n\n"
        f"<b>Как использовать:</b>\n"
        f"1. Добавьте меня в любую группу.\n"
        f"2. Сделай админом с возможностью читать сообщения.\n"
        f"3. Раз в сутки (около полуночи) я буду присылать сводку сообщений за последние 24 часа.\n"
    )
    try:
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logging.exception(f"Ошибка при отправке ответа на /start пользователю {message.from_user.id}: {e}")

# ----> ОБРАБОТЧИК КОМАНДЫ /summary <----
@router.message(Command("summary"))
async def cmd_summary(message: Message):
    """Позволяет любому участнику чата вызвать сводку за последние 24 часа."""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "unknown"
    logging.info(f"Запрошена сводка командой /summary для чата {chat_id} пользователем {user_id}")
    try:
        await send_summary(message.bot, chat_id)
    except Exception as e:
        logging.exception(f"Критическая ошибка при обработке /summary для чата {chat_id}: {e}")
        try:
            await message.reply("❌ Произошла непредвиденная ошибка при запросе сводки.")
        except Exception as send_error:
             logging.error(f"Не удалось отправить сообщение об ошибке /summary в чат {chat_id}: {send_error}")


# ----> ОБРАБОТЧИК ОБЫЧНЫХ ТЕКСТОВЫХ СООБЩЕНИЙ <----
@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """Сохраняет ТОЛЬКО обычные текстовые сообщения (не команды) в БД."""
    if not message.from_user: return
    await register_chat(message.chat.id)
    text_to_save = message.text
    sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"
    timestamp_to_save = message.date
    if timestamp_to_save.tzinfo is None: timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
    elif timestamp_to_save.tzinfo != timezone.utc: timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)
    try:
        await save_message(
            chat_id=message.chat.id, username=sender_name, text=text_to_save, timestamp=timestamp_to_save
        )
    except Exception as e:
        logging.exception(f"Ошибка при сохранении ТЕКСТОВОГО сообщения в БД для чата {message.chat.id}: {e}")


# ----> ОБРАБОТЧИК ПОДПИСЕЙ К МЕДИА (CAPTION) <----
@router.message(F.caption)
async def handle_caption_message(message: Message):
    """Сохраняет ТОЛЬКО подписи к медиа (фото, видео, документы) в БД."""
    if not message.from_user: return
    await register_chat(message.chat.id)
    text_to_save = message.caption
    sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"
    timestamp_to_save = message.date
    if timestamp_to_save.tzinfo is None: timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
    elif timestamp_to_save.tzinfo != timezone.utc: timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)
    try:
        await save_message(
            chat_id=message.chat.id, username=sender_name, text=text_to_save, timestamp=timestamp_to_save
        )
    except Exception as e:
        logging.exception(f"Ошибка при сохранении CAPTION сообщения в БД для чата {message.chat.id}: {e}")

# --- END OF FILE user_handlers.py ---
