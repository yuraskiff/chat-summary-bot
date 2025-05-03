from aiogram import Router, types
from aiogram.filters import Command
from datetime import datetime, timezone

from db.db import save_message
from bot.handlers.admin_handlers import send_summary  # добавлено

router = Router()

@router.message(Command("summary"))
async def cmd_summary(message: types.Message):
    """
    Позволяет любому участнику чата вызвать сводку.
    """
    await send_summary(message.bot, message.chat.id)

@router.message()
async def handle_message(message: types.Message):
    """
    Автоматически регистрируем любой чат при первом сообщении
    и сохраняем текст или подпись в БД.
    """
    from db.db import register_chat  # локальный импорт, чтобы избежать циклов

    # Регистрируем чат
    await register_chat(message.chat.id)

    # Определяем, что сохранять
    text_to_save = None
    if message.text and not message.text.startswith("/"):
        text_to_save = message.text
    elif message.caption:
        text_to_save = message.caption

    # Сохраняем, если есть что сохранять
    if text_to_save:
        await save_message(
            chat_id=message.chat.id,
            username=message.from_user.username or message.from_user.full_name,
            text=text_to_save,
            timestamp=datetime.now(timezone.utc)  # aware datetime
        )
