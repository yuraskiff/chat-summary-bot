from aiogram import Router, types
from aiogram.filters import Command
from bot.utils.helpers import greet_user
from db.db import save_message, register_chat
from datetime import datetime

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    """
    Обрабатывает команду /start:
    - Регистрирует чат (private или group) в таблице chats.
    - Приветствует пользователя.
    """
    # Регистрируем чат для последующих команд администратора
    await register_chat(message.chat.id)
    # Приветственное сообщение
    await message.answer(greet_user(message.from_user.first_name))

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def handle_message(message: types.Message):
    """
    Обрабатывает все текстовые сообщения, кроме команд:
    - Регистрирует чат, если он ещё не зарегистрирован.
    - Сохраняет сообщение в таблице messages с naive UTC-временем.
    """
    # Убедимся, что чат зарегистрирован
    await register_chat(message.chat.id)

    # Сохраняем текстовое сообщение
    await save_message(
        chat_id=message.chat.id,
        username=message.from_user.username or message.from_user.full_name,
        text=message.text,
        timestamp=datetime.utcnow()  # naive UTC datetime
    )
