from aiogram import Router, types
from aiogram.filters import Command
from bot.utils.helpers import greet_user
from db.db import save_message, register_chat
from datetime import datetime, timezone

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    """
    Обрабатывает /start:
    - Регистрирует чат.
    - Приветствует пользователя.
    """
    await register_chat(message.chat.id)
    await message.answer(greet_user(message.from_user.first_name))

@router.message()
async def handle_message(message: types.Message):
    """
    Сохраняет:
      - обычные текстовые сообщения (msg.text),
      - подписи к медиа (msg.caption),
    пропуская команды (/…).
    """
    # Регистрируем чат, если ещё не было
    await register_chat(message.chat.id)

    # Выбираем, что сохранять
    text_to_save = None
    if message.text and not message.text.startswith('/'):
        text_to_save = message.text
    elif message.caption:
        text_to_save = message.caption

    if not text_to_save:
        # Это либо команда, либо чистое медиа без подписи
        return

    # Сохраняем с timezone-aware UTC
    await save_message(
        chat_id=message.chat.id,
        username=message.from_user.username or message.from_user.full_name,
        text=text_to_save,
        timestamp=datetime.now(timezone.utc)
    )
