# --- START OF FILE bot/handlers/user_handlers.py ---

import logging
from datetime import timezone # Импортируем для работы с временными метками

from aiogram import Router, types
from aiogram.filters import Command, CommandStart # Добавили CommandStart

# Импортируем функции из других модулей
from db.db import save_message, register_chat
# Импортируем функцию для вызова сводки
from bot.handlers.admin_handlers import send_summary

router = Router()

# ----> ОБРАБОТЧИК КОМАНДЫ /start <----
@router.message(CommandStart())
async def cmd_start(message: types.Message):
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
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        # Логируем ошибку, но не сообщаем пользователю, если это просто /start
        logging.exception(f"Ошибка при отправке ответа на /start пользователю {message.from_user.id}: {e}")

# ----> ОБРАБОТЧИК КОМАНДЫ /summary <----
# Этот обработчик доступен всем
@router.message(Command("summary"))
async def cmd_summary(message: types.Message):
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
            await message.reply("❌ Произошла непредвиденная ошибка при запросе сводки.")
        except Exception: pass


# ----> ОБЩИЙ ОБРАБОТЧИК СООБЩЕНИЙ (для сохранения) <----
# Регистрируем его без фильтров, чтобы он ловил все, что не поймали команды
@router.message()
async def handle_message(message: Message):
    """
    Автоматически регистрирует чат (если новый)
    и сохраняет текст сообщения или подпись к медиа в БД.
    Игнорирует сообщения, начинающиеся со слеша (команды).
    """
    # Не обрабатываем сообщения без отправителя (например, системные)
    if not message.from_user:
        return

    # Регистрируем чат
    await register_chat(message.chat.id)

    # Определяем текст для сохранения
    text_to_save = None
    if message.text and not message.text.startswith('/'):
        text_to_save = message.text
    elif message.caption:
        text_to_save = message.caption

    if text_to_save:
        timestamp_to_save = message.date
        if timestamp_to_save.tzinfo is None:
            timestamp_to_save = timestamp_to_save.replace(tzinfo=timezone.utc)
        elif timestamp_to_save.tzinfo != timezone.utc:
            timestamp_to_save = timestamp_to_save.astimezone(timezone.utc)

        sender_name = message.from_user.username or message.from_user.full_name or f"User_{message.from_user.id}"

        # Сохраняем в фоне, чтобы не блокировать ответ пользователю (если бы он был)
        # asyncio.create_task(save_message(...)) # Можно так, но для БД лучше await
        try:
            await save_message(
                chat_id=message.chat.id,
                username=sender_name,
                text=text_to_save,
                timestamp=timestamp_to_save
            )
        except Exception as e:
            # Логируем, но не сообщаем пользователю об ошибке сохранения
            logging.exception(f"Ошибка при сохранении сообщения в БД для чата {message.chat.id}: {e}")

# --- END OF FILE bot/handlers/user_handlers.py ---
