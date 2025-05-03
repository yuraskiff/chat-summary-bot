from datetime import datetime, timezone
from aiogram import Router
from aiogram.types import ChatMemberUpdated
from db.db import register_chat

router = Router()

@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated):
    """
    Регистрация чата сразу при добавлении бота в группу.
    """
    old, new = update.old_chat_member, update.new_chat_member
    was_out = old.status in ("left", "kicked")
    is_in = new.status in ("member", "administrator")
    if was_out and is_in:
        # Пример добавления текущего времени (если тебе потребуется это в register_chat)
        current_time = datetime.now(timezone.utc)
        await register_chat(update.chat.id, registered_at=current_time)
