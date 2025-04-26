
from aiogram.dispatcher.middlewares.base import BaseMiddleware
import logging

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        if user_id in [123456789]:  # Example user ID check
            return await handler(event, data)
        else:
            logging.warning(f"Unauthorized access attempt by user_id: {user_id}")
            await event.answer("У вас нет доступа.")
