# --- START OF FILE user_handlers.py ---

import logging
from datetime import timezone # Импортируем для работы с временными метками

from aiogram import Router, types
from aiogram.filters import Command, CommandStart # Добавили CommandStart

# Импортируем функции из других модулей
from db.db import save_message, register_chat
from bot.handlers.admin_handlers import send_summary # Для вызова сводки по команде

router = Router()

# ----> НОВЫЙ ОБРАБОТЧИК КОМАНДЫ /start <----
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start. Отправляет приветственное сообщение.
    Работает только в личных сообщениях или если упомянуть бота в группе.
    """
    user_name = message.from_user.full_name
    # Формируем приветственное сообщение
    # Используем HTML-разметку для выделения
    text = (
        f"Привет, <b>{user_name}</b>!\n\n"
        f"Я бот для создания кратких сводок (summary) в групповых чатах.\n\n"
        f"<b>Как использовать:</b>\n"
        f"1. Добавьте меня в любую группу.\n"
        f"2. Я буду автоматически сохранять сообщения.\n"
        f"3. Раз в сутки (около полуночи по времени сервера) я буду присылать сводку сообщений за последние 24 часа.\n"
        f"4. Вы также можете запросить сводку за последние 24 часа в любое время командой <code>/summary</code> прямо в группе.\n\n"
        f"Для администратора бота доступны дополнительные команды (в личном чате с ботом или в группе): <code>/chats</code>, <code>/pdf <chat_id></code>, <code>/set_prompt <текст></code>."
    )
    try:
        await message.reply(text, parse_mode="HTML") # Указываем parse_mode
    except Exception as e:
        logging.error(f"Ошибка при отправке ответа на /start пользователю {message.from_user.id}: {e}")

# ----> ОБРАБОТЧИК КОМАНДЫ /summary <----
@router.message(Command("summary"))
async def cmd_summary(message: types.Message):
    """
    Позволяет любому участнику чата вызвать сводку за последние 24 часа.
    """
    # Эта команда имеет смысл только в группах, но для простоты вызываем для любого чата
    logging.info(f"Запрошена сводка командой /summary для чата {message.chat.id} пользователем {message.from_user.id}")
    # Вызываем общую функцию отправки сводки из admin_handlers
    await send_summary(message.bot, message.chat.id)


# ----> ОБЩИЙ ОБРАБОТЧИК СООБЩЕНИЙ (для сохранения) <----
# Важно: Этот хэндлер должен идти ПОСЛЕ обработчиков команд,
# чтобы не перехватывать их. aiogram обрабатывает в порядке добавления/декорирования.
@router.message()
async def handle_message(message: types.Message):
    """
    Автоматически регистрирует чат (если новый)
    и сохраняет текст сообщения или подпись к медиа в БД.
    Игнорирует сообщения, начинающиеся со слеша (команды).
    """
    # Регистрируем чат (если его нет, он добавится; если есть, ничего не произойдет)
    await register_chat(message.chat.id)

    # Определяем текст для сохранения
    text_to_save = None
    # Сохраняем только если есть текст и он не начинается с "/"
    if message.text and not message.text.startswith('/'):
        text_to_save = message.text
    # Или если есть подпись к медиа
    elif message.caption:
        text_to_save = message.caption

    # Сохраняем, если есть что сохранять и есть информация об отправителе
    if text_to_save and message.from_user:
        # message.date от Telegram уже является aware datetime (обычно UTC)
        timestamp_to_save = message.date
        # Дополнительная проверка и установка UTC для надежности
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
            # Логируем факт сохранения (опционально, может быть слишком много логов)
            # logging.info(f"Сохранено сообщение от {sender_name} в чате {message.chat.id}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении сообщения в БД для чата {message.chat.id}: {e}")

    # Важно: этот хэндлер не отвечает пользователю, он только сохраняет сообщение.
    # Ответы дают только обработчики команд (/start, /summary).

# --- END OF FILE user_handlers.py ---
