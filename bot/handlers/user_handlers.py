# --- START OF FILE user_handlers.py ---

import logging
from datetime import timezone # Импортируем для работы с временными метками

from aiogram import Router
# ----> ИЗМЕНЕННЫЙ ИМПОРТ <----
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

# Импортируем функции из других модулей
from db.db import save_message, register_chat
# Импортируем функцию для вызова сводки
from bot.handlers.admin_handlers import send_summary

router = Router()

# ----> ОБРАБОТЧИК КОМАНДЫ /start <----
# Используем Message напрямую
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
# Используем Message напрямую
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


# ----> ОБЩИЙ ОБРАБОТЧИК СООБЩЕНИЙ (для сохранения) <----
# Используем Message напрямую
@router.message()
async def handle_message(message: Message):
    """
    Автоматически регистрирует чат (если новый)
    и сохраняет текст сообщения или подпись к медиа в БД.
    Игнорирует сообщения, начинающиеся со слеша (команды).
    """
    # Не обрабатываем сообщения без отправителя (например, системные канальные посты)
    if not message.from_user:
        return

    # Регистрируем чат (ON CONFLICT DO NOTHING в db.py)
    await register_chat(message.chat.id)

    # Определяем текст для сохранения
    text_to_save = None
    # Сохраняем только если есть текст и он не начинается с "/"
    if message.text and not message.text.startswith('/'):
        text_to_save = message.text
    # Или если есть подпись к медиа
    elif message.caption:
        text_to_save = message.caption

    # Сохраняем, если есть что сохранять
    if text_to_save:
        # Используем message.date (aware datetime от Telegram)
        timestamp_to_save = message.date
        # Дополнительная проверка и приведение к UTC для надежности
        if timestamp_to_save.tzinfo is None:
            timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
        elif timestamp_to_save.tzinfo != timezone.utc:
            timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)

        # Определяем имя пользователя (username или full_name, или ID как fallback)
        sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"

        try:
            await save_message(
                chat_id=message.chat.id,
                username=sender_name,
                text=text_to_save,
                timestamp=timestamp_to_save # Передаем aware datetime
            )
        except Exception as e:
            # Логируем ошибку сохранения, но не беспокоим пользователя
            logging.exception(f"Ошибка при сохранении сообщения в БД для чата {message.chat.id}: {e}")

# --- END OF FILE user_handlers.py ---
