from aiogram import Router, types
from aiogram.filters import Command
from bot.utils.helpers import greet_user
from db.db import save_message
from datetime import datetime

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    """
    Приветственный хендлер: отвечает на /start.
    """
    await message.answer(greet_user(message.from_user.first_name))

@router.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def handle_message(message: types.Message):
    """
    Хендлер для всех текстовых сообщений (не команд).
    Сохраняет сообщение в БД с naive UTC-временем.
    """
    await save_message(
        chat_id=message.chat.id,
        username=message.from_user.username or message.from_user.full_name,
        text=message.text,
        timestamp=datetime.utcnow()  # naive UTC datetime
    )
