# --- START OF FILE bot/middleware/auth_middleware.py ---

import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from config.config import ADMIN_CHAT_ID # Убедитесь, что импорт корректен

class AuthMiddleware(BaseMiddleware):
    """
    Middleware для базовой авторизации админ-команд.
    - Пропускает все не-команды или команды, не являющиеся админскими.
    - Пропускает админ-команды, если их вызвал ADMIN_CHAT_ID.
    - Блокирует (не передает дальше) админ-команды от других пользователей.
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message, # Указываем тип event как Message для message middleware
        data: Dict[str, Any]
    ) -> Any:

        # Проверяем, что ADMIN_CHAT_ID вообще задан
        if ADMIN_CHAT_ID is None:
             # Если админ не задан, пропускаем все команды (не безопасно!)
             # Или можно блокировать все админские команды
             logging.warning("ADMIN_CHAT_ID не задан, AuthMiddleware пропускает все.")
             return await handler(event, data)

        # Получаем пользователя из события Message
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            # Сообщения без пользователя (например, системные) пропускаем
            return await handler(event, data)

        # Получаем текст сообщения (если есть)
        text = event.text
        if not text:
            # Сообщения без текста (стикеры, фото без подписи и т.д.) пропускаем
            return await handler(event, data)

        # Приводим к нижнему регистру и убираем пробелы в начале
        command_text = text.lstrip().lower()

        # Список админ-команд (без параметров)
        admin_commands_start = ("/chats", "/pdf", "/set_prompt")

        is_admin_command = False
        for cmd in admin_commands_start:
            if command_text.startswith(cmd):
                is_admin_command = True
                break

        # Если это админ-команда и пользователь НЕ админ
        if is_admin_command and user_id != ADMIN_CHAT_ID:
            logging.info(f"Пользователь {user_id} попытался выполнить админ-команду: {command_text.split()[0]}")
            # Просто не вызываем следующий хэндлер (handler)
            # Сообщение будет проигнорировано ботом
            return None # Или можно отправить сообщение "Нет доступа"
            # await event.reply("У вас нет прав для выполнения этой команды.")
            # return None
        else:
            # Если это не админ-команда ИЛИ пользователь является админом,
            # передаем управление следующему хэндлеру
            return await handler(event, data)

# --- END OF FILE bot/middleware/auth_middleware.py ---
