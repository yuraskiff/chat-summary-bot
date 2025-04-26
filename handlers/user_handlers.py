
from aiogram import Router, types
from aiogram.filters import Command
from bot.utils.helpers import greet_user

router = Router()

@router.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(greet_user(message.from_user.first_name))
