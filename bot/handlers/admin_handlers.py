from aiogram import Router, types
from aiogram.filters import Command
from db.db import fetch, execute
from api_clients.openrouter import generate_summary
from utils.helpers import generate_chat_pdf
import tempfile

router = Router()

@router.message(Command('list_chats'))
async def list_chats(message: types.Message):
    rows = await fetch("SELECT chat_id FROM chats;")
    if not rows:
        return await message.answer("Нет сохранённых чатов.")
    text = "Список чатов:\n" + '\n'.join(str(r['chat_id']) for r in rows)
    await message.answer(text)

@router.message(Command('get_pdf'))
async def get_pdf(message: types.Message):
    args = message.get_args().split()
    if not args:
        return await message.answer("Использование: /get_pdf <chat_id>")
    chat_id = int(args[0])
    msgs = await fetch(
        "SELECT user_name, content, created_at FROM messages WHERE chat_id=$1 ORDER BY created_at;", chat_id
    )
    if not msgs:
        return await message.answer("Сообщений нет.")
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tf:
        await generate_chat_pdf(tf.name, chat_id, msgs)
        await message.answer_document(open(tf.name, 'rb'))

@router.message(Command('change_summary_type'))
async def change_summary_type(message: types.Message):
    new_type = message.get_args().strip()
    if not new_type:
        return await message.answer("Использование: /change_summary_type <тип>")
    await execute(
        "INSERT INTO settings(key,value) VALUES('summary_type',$1) "
        "ON CONFLICT(key) DO UPDATE SET value=$1;", new_type
    )
    await message.answer(f"Тип суммаризации обновлён: {new_type}")
