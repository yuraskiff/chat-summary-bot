from aiogram.dispatcher.middlewares.base import BaseMiddleware
import logging
from config.config import ADMIN_CHAT_ID

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        if user_id == ADMIN_CHAT_ID:
            return await handler(event, data)
        logging.warning(f"Unauthorized access: {user_id}")
        await event.answer("У вас нет доступа.")
