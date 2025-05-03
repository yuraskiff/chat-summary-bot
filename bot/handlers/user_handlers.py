from aiogram import Router, types
from db.db import save_message
from datetime import datetime, timezone

router = Router()

@router.message()
async def handle_message(message: types.Message):
    """
    Автоматически регистрируем любой чат при первом текстовом или
    медиа-подписи и сохраняем текст или подпись в БД.
    """
    from db.db import register_chat  # локальный импорт, чтобы не было циклов

    # 1. Регистрируем чат
    await register_chat(message.chat.id)

    # 2. Определяем, что сохранять
    text_to_save = None
    if message.text and not message.text.startswith('/'):
        text_to_save = message.text
    elif message.caption:
        text_to_save = message.caption

    # 3. Сохраняем, если есть что сохранять
    if text_to_save:
        await save_message(
            chat_id=message.chat.id,
            username=message.from_user.username or message.from_user.full_name,
            text=text_to_save,
            timestamp=datetime.now(timezone.utc)  # вот здесь исправлено
        )
