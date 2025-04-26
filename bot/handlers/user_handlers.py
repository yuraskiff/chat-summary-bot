from aiogram import Router, types
from aiogram.filters import Command
from db.db import execute
from utils.helpers import greet_user

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(greet_user(message.from_user.first_name))

@router.message()
async def log_message(message: types.Message):
    # сохраняем чат и сообщение
    await execute("INSERT INTO chats(chat_id) VALUES($1) ON CONFLICT DO NOTHING;", message.chat.id)
    await execute(
        "INSERT INTO messages(chat_id, user_id, user_name, content) VALUES($1,$2,$3,$4);",
        message.chat.id,
        message.from_user.id,
        message.from_user.full_name,
        message.text or ''
    )
