from aiogram import BaseMiddleware
from aiogram.types import Message
from config.config import ADMIN_CHAT_ID

class AuthMiddleware(BaseMiddleware):
    """
    Middleware, которое пускает все сообщения и команду /summary,
    но блокирует выполнение админ-команд (/chats, /pdf, /set_prompt)
    для всех пользователей, кроме ADMIN_CHAT_ID.
    """
    async def __call__(self, handler, event, data):
        message: Message = data.get("message")
        # Если нет текстового сообщения — пропускаем дальше
        if not message or not message.text:
            return await handler(event, data)

        text = message.text.lstrip().lower()

        # Админ-команды, к которым нужен доп. допуск
        admin_commands = ("/chats", "/pdf", "/set_prompt")

        # Если это одна из админ-команд
        if any(text.startswith(cmd) for cmd in admin_commands):
            # и не наш админ — просто игнорируем
            if message.from_user.id != ADMIN_CHAT_ID:
                return

        # Всё остальное (включая /summary и обычные тексты) обрабатываем
        return await handler(event, data)
