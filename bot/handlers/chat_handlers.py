# --- START OF FILE bot/handlers/chat_handlers.py ---

import logging
from aiogram import Router
from aiogram.types import ChatMemberUpdated
from db.db import register_chat

router = Router()

@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated):
    """Регистрация чата при добавлении бота в группу."""
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    chat_id = update.chat.id

    logging.info(f"Статус бота в чате {chat_id} изменен: {old_status} -> {new_status}")

    # Условие: Бота именно ДОБАВИЛИ (или он был кикнут/вышел и вернулся)
    if old_status in ("left", "kicked") and new_status in ("member", "administrator", "creator"):
        logging.info(f"Бота добавили в чат {chat_id}. Регистрация...")
        await register_chat(chat_id)
    elif old_status in ("member", "administrator", "creator") and new_status in ("left", "kicked"):
         logging.info(f"Бота удалили или кикнули из чата {chat_id}.")
         # Здесь можно добавить логику удаления чата из registered_chats, если нужно
         # await unregister_chat(chat_id) # Потребуется новая функция в db.py

# --- END OF FILE bot/handlers/chat_handlers.py ---
